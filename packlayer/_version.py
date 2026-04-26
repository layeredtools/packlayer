from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("packlayer")
except PackageNotFoundError:
    __version__ = "dev"
