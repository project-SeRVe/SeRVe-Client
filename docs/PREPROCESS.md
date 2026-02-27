# Robot Log Preprocessing

## Overview

The `serve data preprocess` command converts raw robot trajectory logs into the canonical NPZ format required by SeRVe-Client's vector DB and VLA inference pipeline.

## Command

```bash
serve data preprocess INPUT_DIR [OUTPUT_DIR] [OPTIONS]
```

### Arguments

- `INPUT_DIR`: Directory containing demo folders (or scenario directories if `--recursive`)
- `OUTPUT_DIR`: Optional output directory (defaults to INPUT_DIR)

### Options

- `--prompt TEXT`: Task prompt(s) to use (can be specified multiple times for random selection)
- `--wrist-camera TEXT`: Wrist camera subdirectory name (default: `hand_camera`)
- `--base-camera TEXT`: Base camera subdirectory name (default: `varied_camera_1`)
- `--rotate-180`: Rotate images 180 degrees before resizing
- `--overwrite`: Overwrite existing `processed_demo.npz` files
- `--placeholder-embeddings`: Use zero embeddings (no GPU required) - **NOT for production**
- `--recursive`: Process all scenario subdirectories in INPUT_DIR

## Input Structure

### Single Scenario Mode (default)

```
input-dir/
├── demo_0/
│   ├── traj.h5 (or trajectory.h5)
│   └── recordings/
│       └── frames/
│           ├── hand_camera/
│           │   ├── 000.jpg
│           │   ├── 001.jpg
│           │   └── ...
│           └── varied_camera_1/
│               ├── 000.jpg
│               ├── 001.jpg
│               └── ...
├── demo_1/
│   └── ...
└── ...
```

### Recursive Mode (`--recursive`)

```
input-dir/
├── 2025-01-15_pick_cube/
│   ├── demo_0/
│   │   ├── traj.h5
│   │   └── recordings/...
│   ├── demo_1/
│   └── ...
├── 2025-01-16_stack_blocks/
│   ├── demo_0/
│   └── ...
└── ...
```

## Output

Each demo folder gets:

1. **`processed_demo.npz`** - Canonical format NPZ file containing:
   - `state`: (T, 8) - Joint positions (7) + gripper (1)
   - `actions`: (T, 7) - Joint velocities (6) + gripper (1)
   - `base_image`: (T, 224, 224, 3) - RGB images from base camera
   - `wrist_image`: (T, 224, 224, 3) - RGB images from wrist camera
   - `base_image_embeddings`: (T, D) - DINOv2 embeddings of base images
   - `wrist_image_embeddings`: (T, D) - DINOv2 embeddings of wrist images
   - `prompt`: string - Task description

2. **`episode_meta.json`** - Metadata file:
   ```json
   {
     "source": "robot_raw",
     "trajectory_file": "traj.h5",
     "num_steps": 150,
     "state_dim": 8,
     "action_dim": 7,
     "base_camera": "varied_camera_1",
     "wrist_camera": "hand_camera",
     "rotate_180": false,
     "embedding_type": "dinov2"
   }
   ```

## Examples

### Basic Usage (Single Scenario)

```bash
# Process demos with explicit prompt
serve data preprocess ./raw_demos --prompt "pick up the cube"

# Process demos and infer prompt from meta.json or directory name
serve data preprocess ./2025-01-15_pick_cube
```

### Recursive Processing

```bash
# Process multiple scenarios (prompts inferred from directory names)
serve data preprocess ./all_scenarios --recursive

# Process with custom cameras
serve data preprocess ./all_scenarios --recursive \
  --wrist-camera hand_camera \
  --base-camera base_camera_1
```

### Quick Testing (No GPU)

```bash
# Use placeholder embeddings for structure validation only
serve data preprocess ./raw_demos --placeholder-embeddings

# WARNING: Placeholder embeddings are zeros - NOT suitable for production!
```

### Overwrite Mode

```bash
# Reprocess existing demos
serve data preprocess ./raw_demos --overwrite
```

## Workflow Integration

After preprocessing, use the processed demos:

### 1. Upload to SeRVe Server

```bash
# Upload single scenario
serve data upload-scenario <team-id> pick_cube ./2025-01-15_pick_cube

# Upload multiple scenarios
for scenario in ./scenarios/*/; do
  scenario_name=$(basename "$scenario")
  serve data upload-scenario <team-id> "$scenario_name" "$scenario"
done
```

### 2. Build Vector DB (Next Step)

```bash
# Build local vector DB from downloaded demos
serve data build-index <team-id>
```

### 3. Run Inference

```bash
# Use demos for RAG-based VLA inference
serve reasoning few-shot <robot> "pick up the red cube"
```

## Technical Details

### DINOv2 Embeddings

- **Model**: `facebook/dinov2-base` (ViT-B/14)
- **Embedding Type**: 64PATCHES (default) - 64 spatial patches × 768D = 49,152D total
- **Alternatives**: Set `EMBEDDING_TYPE` in `dinov2_utils.py`:
  - `CLS`: 768D (CLS token only)
  - `AVG`: 768D (average of all patches)
  - `16PATCHES`: 12,288D (16 patches)

### Image Preprocessing

1. Load RGB frames from camera directories
2. Convert to uint8 format if needed
3. Resize to 224×224 with padding (aspect ratio preserved)
4. Rotate 180° if `--rotate-180` flag set
5. Normalize with ImageNet mean/std
6. Extract DINOv2 embeddings

### Trajectory Processing

1. Read H5 file (observation + action data)
2. Extract joint positions → state (8D)
3. Extract joint velocities → actions (7D)
4. Apply `skip_action` mask if present
5. Validate shape consistency

### Prompt Inference Priority

1. Explicit `--prompt` option (random if multiple)
2. `meta.json` file in demo directory (`prompt` field)
3. Parent directory name (e.g., `2025-01-15_pick_cube` → "pick cube")

## Troubleshooting

### Missing Camera Frames

```
FileNotFoundError: Missing camera directory: .../recordings/frames/hand_camera
```

**Solution**: Check camera naming. Use `--wrist-camera` and `--base-camera` options to match your setup.

### Frame Count Mismatch

```
ValueError: Frame count mismatch for hand_camera: 120 vs expected 150
```

**Solution**: Ensure frame extraction from SVO files matches trajectory length. Check if frames were dropped during recording.

### Out of Memory (GPU)

```
RuntimeError: CUDA out of memory
```

**Solutions**:
1. Reduce batch size in `embed_with_batches()` (default: 256)
2. Process fewer demos at once
3. Use `--placeholder-embeddings` for initial testing (CPU only)

### Import Errors

```
ModuleNotFoundError: No module named 'h5py'
```

**Solution**: Reinstall dependencies:
```bash
pip install -e .
```

## Performance

- **DINOv2 on GPU**: ~500 frames/sec (RTX 3090)
- **DINOv2 on CPU**: ~20 frames/sec
- **Typical demo**: 100-200 steps → 2-4 seconds/demo (GPU)

## Dependencies

- `numpy`: Array operations
- `h5py`: Read trajectory H5 files
- `Pillow`: Image loading and resizing
- `torch`: DINOv2 inference
- `torchvision`: Image normalization

## Next Steps

After preprocessing:

1. ✅ **Validate**: `serve data validate <demo-dir>` (coming soon)
2. ✅ **Upload**: `serve data upload-scenario <team-id> <scenario> <dir>`
3. ⏳ **Build Index**: `serve data build-index <team-id>` (coming soon)
4. ⏳ **Inference**: `serve reasoning few-shot <robot> <text>` (coming soon)
