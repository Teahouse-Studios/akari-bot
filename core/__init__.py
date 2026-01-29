import sys

python_version = (3, 12)


def check_python_version():
    if sys.version_info[:2] < python_version:
        major, minor = sys.version_info[:2]
        raise RuntimeError(
            "Your Python version is {}.{}, "
            "but Python {}.{} or higher is required.".format(
                major,
                minor,
                *python_version
            )  # noqa
        )
