import click
from .auth import auth
from .repo import repo
from .data import data
from .reasoning import reasoning

@click.group()
def cli():
    """
    SeRVe Zero-Trust CLI Client
    
    서버와 클라이언트 간 End-to-End 암호화를 지원하는 문서/데이터 공유 플랫폼
    """
    pass

cli.add_command(auth)
cli.add_command(repo)
cli.add_command(data)
cli.add_command(reasoning)

if __name__ == "__main__":
    cli()
