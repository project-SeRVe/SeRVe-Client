from setuptools import setup, find_packages

setup(
    name='serve',
    version='0.1.0',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[
        'click',
        'rich',
        'requests',
        'tink',
        'cryptography',  # 비밀번호 기반 개인키 암호화에 사용
        'numpy',
        'h5py',
        'Pillow',
        'torch',
        'torchvision'
    ],
    entry_points='''
        [console_scripts]
        serve=cli.main:cli
    ''',
)
