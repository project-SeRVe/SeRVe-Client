import click
from .context import CLIContext

@click.group()
def reasoning():
    """VLA 추론"""
    pass

@reasoning.command(name="few-shot")
@click.argument('robot')
@click.argument('text')
def few_shot(robot, text):
    """비슷한 데모 동영상을 참고하여 추론"""
    ctx = CLIContext()
    ctx.ensure_authenticated()

    click.echo(f"[+] Reasoning (Few-Shot) on {robot}...")
    click.echo(f"    - Text: {text}")
    # Mock result
    click.echo(click.style(f"✅ 추론 완료: [Actuation commands would appear here]", fg="green"))

@reasoning.command(name="basic")
@click.argument('robot')
@click.argument('text')
def basic(robot, text):
    """모델만으로 추론"""
    ctx = CLIContext()
    ctx.ensure_authenticated()

    click.echo(f"[+] Reasoning (Basic) on {robot}...")
    click.echo(f"    - Text: {text}")
    # Mock result
    click.echo(click.style(f"✅ 추론 완료: [Actuation commands would appear here]", fg="green"))
