import asyncio
import json
import os
import re
import shutil
import traceback
from pathlib import Path
from typing import Optional

import tomllib
from packageurl import PackageURL

INLINE_DEPS_REGEX = (
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$"
)


def load_inline_deps(script: str) -> dict | None:
    name = "script"
    matches = list(
        filter(
            lambda m: m.group("type") == name, re.finditer(INLINE_DEPS_REGEX, script)
        )
    )
    if len(matches) > 1:
        raise ValueError(f"Multiple {name} blocks found")
    elif len(matches) == 1:
        content = "".join(
            line[2:] if line.startswith("# ") else line[1:]
            for line in matches[0].group("content").splitlines(keepends=True)
        )
        return tomllib.loads(content)
    else:
        return None


def ignore_venv(directory: Path, contents: list[str]) -> list[str]:
    if ".venv" in directory:
        return contents
    elif "__pycache__" in directory:
        return contents
    return []


def symlink_tree(src, dst, symlinks=True, ignore=None):
    """
    Create symbolic links of files and directories from src to dst,
    mimicking shutil.copytree but for symlinks.

    :param src: Source directory path
    :param dst: Destination directory path
    :param symlinks: Whether to create symlinks or copy files (default is True for symlinks)
    :param ignore: Callable that can return a list of names to ignore, like shutil.copytree's ignore
    """
    os.makedirs(dst, exist_ok=True)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if ignore and item in ignore(src, [item]):
            continue
        if os.path.isdir(s):
            # Recurse into directories
            symlink_tree(s, d, symlinks, ignore)
        else:
            if symlinks:
                os.symlink(s, d)
            else:
                shutil.copy2(s, d)


async def download_purl(url: str):
    purl = PackageURL.from_string(url)
    if purl.type == "mod":
        if not (Path("/mods") / purl.name).exists():
            raise ValueError(f"Mod {purl.name} not found")
        symlink_tree(f"/mods/{purl.name}", "/app/src", ignore=ignore_venv)
        symlink_tree("/sdk", "/app/src/sdk", ignore=ignore_venv)
        return purl
    elif purl.type in ("github", "gitlab"):
        repo_url = f"https://{purl.type}.com/{purl.namespace}/{purl.name}.git"
        # TODO: Handle subpaths
        await clone_git_repo(repo_url, purl.version)
        return purl
    elif purl.type == "gist":
        await clone_git_repo(f"https://gist.github.com/{purl.name}.git")
        return purl
    else:
        raise ValueError(f"Unsupported package type: {purl.type}")


def guess_entry_point(directory: Path) -> Optional[Path]:
    entry_files = {"app.py", "main.py", "__main__.py"}
    other_files = set()

    for file in directory.iterdir():
        if file.is_file():
            if file.name in entry_files:
                return file
            elif file.name.endswith(".py"):
                other_files.add(file)

    if len(other_files) == 1:
        return other_files.pop()

    return None


def find_deps(directory: Path, entrypoint: Optional[Path] = None) -> Optional[Path]:
    if entrypoint is not None:
        deps = load_inline_deps(entrypoint.read_text())
        if deps is not None:
            with open(directory / "requirements.in", "w") as f:
                for dep in deps["dependencies"]:
                    f.write(f"{dep}\n")

    dep_files = {"requirements.in", "requirements.txt", "pyproject.toml"}
    for file in directory.iterdir():
        if file.is_file():
            if file.name in dep_files:
                return file


async def find_entrypoint_and_deps(
    purl: PackageURL,
) -> tuple[Path, Optional[Path]]:
    base = Path.cwd() / "src"
    if purl.subpath is not None:
        subpath = (base / purl.subpath).resolve()
        # Ensure the resolved user path is within the current working directory
        if not subpath.is_relative_to(base):
            raise ValueError("Invalid path: path traversal detected.")
        if subpath.is_dir():
            entrypoint = guess_entry_point(subpath)
            find_deps(subpath, entrypoint)
        elif subpath.exists():
            entrypoint = subpath
    else:
        entrypoint = guess_entry_point(base)
    return entrypoint, find_deps(base, entrypoint)


def is_valid_git_url(url: str) -> bool:
    # Basic validation to check if the URL looks like a git repo
    git_url_pattern = re.compile(r"^(https?|git)://[\w.@:/\-~]+\.git$")
    return re.match(git_url_pattern, url) is not None


async def clone_git_repo(url: str, version: Optional[str] = None):
    if not is_valid_git_url(url):
        raise ValueError("Invalid git URL")
    git_args = ["git", "clone", "--depth", "1"]
    if version is not None:
        git_args.extend(["--branch", version])
    git_args.extend([url, "src"])
    process = await asyncio.create_subprocess_exec(*git_args)
    await process.wait()


async def install_deps(deps_file: Path):
    os.chdir("/app/src")
    # TODO: decide if we want to clear this out
    if not os.path.exists(".venv") or not os.listdir(".venv"):
        print("Creating new virtual environment...")
        process = await asyncio.create_subprocess_exec("uv", "venv")
        await process.wait()
    print(f"Installing dependencies from {deps_file}...")
    if deps_file.name == "pyproject.toml":
        process = await asyncio.create_subprocess_exec(
            "uv", "sync", "--no-dev", "--frozen"
        )
        await process.wait()
        # Install our SDK / mod helpers
        process = await asyncio.create_subprocess_exec(
            "uv",
            "pip",
            "install",
            "--editable",
            "/app/src/sdk",
        )
    else:
        process = await asyncio.create_subprocess_exec(
            "uv",
            "pip",
            "install",
            "-r",
            str(deps_file),
        )
    await process.wait()


async def main():
    purl_str = os.getenv("PURL")
    flavor = None
    os.environ["VIRTUAL_ENV"] = "/app/src/.venv"
    os.environ["PORT"] = os.getenv("PORT", "6637")  # M O D S
    if purl_str is None:
        print("No PURL provided, rendering welcome mod")
        shutil.copytree("/mods/welcome", "/app/src")
        entrypoint, deps_file = ["app.py"], Path("/app/src/pyproject.toml")
        await install_deps(deps_file)
    else:
        try:
            print(f"Downloading app {purl_str}...")
            purl = await download_purl(purl_str)
            entrypoint, deps_file = await find_entrypoint_and_deps(purl)
            if deps_file == Path("/app/src/pyproject.toml"):
                with open(deps_file, "rb") as f:
                    pyproject = tomllib.load(f)
                tool = pyproject.get("tool", {})
                weave_config = tool.get("weave", {"mod": {}})
                flavor = weave_config["mod"]["flavor"]
                # TODO: this won't really work for custom mods
                if weave_config["mod"].get("entrypoint") is not None:
                    entrypoint = weave_config["mod"]["entrypoint"]
                    if isinstance(entrypoint, str):
                        entrypoint = [entrypoint]
            if isinstance(entrypoint, Path):
                entrypoint = [str(entrypoint)]
            elif entrypoint is None:
                raise ValueError("No entrypoint found")
            if deps_file is not None:
                await install_deps(deps_file)
        except Exception as e:
            print(f"Error building app: {e}")
            traceback.print_exc()
            return
    if flavor is None:
        file_to_check = deps_file or entrypoint[0]
        if os.path.exists(file_to_check):
            contents = Path(file_to_check).read_text()
            if "streamlit" in contents:
                flavor = "streamlit"
            elif "marimo" in contents:
                flavor = "marimo"
            elif "fasthtml" in contents:
                flavor = "fasthtml"
            else:
                raise ValueError("Unable to determine mod flavor")
        else:
            raise ValueError("Unable to determine mod flavor")
    if flavor == "streamlit":
        args = [
            "uv",
            "run",
            "--no-project",
            "streamlit",
            "run",
            *entrypoint,
            "--server.port=" + os.getenv("PORT"),
            "--server.address=0.0.0.0",
            "--server.enableCORS=false",
            "--server.enableXsrfProtection=false",
            "--client.toolbarMode=developer",
        ]
    elif flavor == "marimo":
        args = [
            "uv",
            "run",
            "--no-project",
            "marimo",
            "run",
            "--port=" + os.getenv("PORT"),
            "--host=0.0.0.0",
            *entrypoint,
        ]
    elif flavor == "fasthtml":
        args = ["uv", "run", "--no-project", *entrypoint]
    elif flavor == "custom":
        args = ["uv", "run", "--no-project", *entrypoint]
    else:
        raise ValueError(f"Unsupported flavor: {flavor}")
    print(f"Running {flavor} app from {os.getcwd()}: {" ".join(args)}")
    with open("/tmp/mod-ready", "w") as f:
        f.write(f"ready: {json.dumps(args)}")
    os.execvp("uv", args)


if __name__ == "__main__":
    asyncio.run(main())
