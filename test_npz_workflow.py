"""
Test script for NPZ file handling workflow.

This script creates a sample robot trajectory NPZ file and tests the
npz_to_chunks and chunks_to_npz utilities.
"""

import numpy as np
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from cli.npz_utils import npz_to_chunks, chunks_to_npz


def create_sample_trajectory_npz(output_path: str):
    """Create a sample robot trajectory NPZ file for testing."""
    # Simulate robot trajectory data
    timestamps = np.linspace(0, 10, 100)  # 100 timesteps over 10 seconds
    joint_positions = np.random.rand(100, 7)  # 7-DOF robot, 100 timesteps
    joint_velocities = np.random.rand(100, 7)
    end_effector_pose = np.random.rand(100, 6)  # xyz + rpy
    gripper_state = np.random.randint(0, 2, 100)  # binary open/closed
    
    np.savez(
        output_path,
        timestamps=timestamps,
        joint_positions=joint_positions,
        joint_velocities=joint_velocities,
        end_effector_pose=end_effector_pose,
        gripper_state=gripper_state
    )
    print(f"✅ Created sample trajectory NPZ: {output_path}")


def test_npz_workflow():
    """Test the complete NPZ upload/download workflow."""
    test_npz = "test_trajectory.npz"
    output_npz = "test_trajectory_restored.npz"
    
    try:
        # Step 1: Create sample NPZ file
        print("\n=== Step 1: Creating sample robot trajectory ===")
        create_sample_trajectory_npz(test_npz)
        
        # Step 2: Serialize to chunks (simulating upload)
        print("\n=== Step 2: Serializing NPZ to encrypted chunks ===")
        chunks = npz_to_chunks(test_npz, chunk_size_kb=64)
        print(f"✅ NPZ split into {len(chunks)} chunks")
        total_size = sum(len(c['data']) for c in chunks)
        print(f"   Total encoded size: {total_size / 1024:.2f} KB")
        
        # Step 3: Deserialize from chunks (simulating download)
        print("\n=== Step 3: Deserializing chunks back to NPZ ===")
        chunks_to_npz(chunks, output_npz)
        print(f"✅ NPZ file restored: {output_npz}")
        
        # Step 4: Verify data integrity
        print("\n=== Step 4: Verifying data integrity ===")
        with np.load(test_npz) as original:
            with np.load(output_npz) as restored:
                # Check all arrays match
                for key in original.files:
                    if not np.allclose(original[key], restored[key]):
                        print(f"❌ Mismatch in array: {key}")
                        return False
                print(f"✅ All arrays verified ({len(original.files)} arrays)")
                print(f"   Arrays: {', '.join(original.files)}")
        
        print("\n✅ NPZ workflow test PASSED!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        if os.path.exists(test_npz):
            os.remove(test_npz)
        if os.path.exists(output_npz):
            os.remove(output_npz)
        print("\n=== Cleanup complete ===")


if __name__ == "__main__":
    success = test_npz_workflow()
    sys.exit(0 if success else 1)
