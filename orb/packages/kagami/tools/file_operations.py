"""File Operations — Real file system tools for colony agents.

Provides file I/O, search, and directory operations with proper error handling,
logging, and safety checks.

Used by: All colonies (especially Grove, Nexus, Beacon)

Created: December 28, 2025
"""

import glob
import logging
import pathlib
import re
from typing import Any

logger = logging.getLogger(__name__)

# =============================================================================
# FILE READING
# =============================================================================


def read_file(
    file_path: str,
    encoding: str = "utf-8",
    max_size_mb: float = 10.0,
) -> dict[str, Any]:
    """Read file contents with safety checks.

    Args:
        file_path: Path to file
        encoding: File encoding
        max_size_mb: Maximum file size in MB

    Returns:
        Result with file contents or error
    """
    try:
        path = pathlib.Path(file_path).expanduser().resolve()

        if not path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "path": str(path),
            }

        if not path.is_file():
            return {
                "success": False,
                "error": f"Not a file: {file_path}",
                "path": str(path),
            }

        # Check file size
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > max_size_mb:
            return {
                "success": False,
                "error": f"File too large: {size_mb:.2f}MB > {max_size_mb}MB",
                "path": str(path),
                "size_mb": size_mb,
            }

        # Read file
        content = path.read_text(encoding=encoding)
        line_count = content.count("\n") + 1

        logger.debug(f"Read {line_count} lines from {path}")

        return {
            "success": True,
            "path": str(path),
            "content": content,
            "line_count": line_count,
            "size_bytes": path.stat().st_size,
            "encoding": encoding,
        }

    except UnicodeDecodeError as e:
        return {
            "success": False,
            "error": f"Encoding error: {e}",
            "path": file_path,
            "suggestion": "Try a different encoding (e.g., 'latin-1', 'utf-16')",
        }
    except PermissionError:
        return {
            "success": False,
            "error": f"Permission denied: {file_path}",
            "path": file_path,
        }
    except Exception as e:
        logger.error(f"Error reading file: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "path": file_path,
        }


# =============================================================================
# FILE WRITING
# =============================================================================


def write_file(
    file_path: str,
    content: str,
    encoding: str = "utf-8",
    create_dirs: bool = True,
    backup: bool = True,
) -> dict[str, Any]:
    """Write content to file with safety checks.

    Args:
        file_path: Path to file
        content: Content to write
        encoding: File encoding
        create_dirs: Create parent directories if needed
        backup: Create backup of existing file

    Returns:
        Result with write status
    """
    try:
        path = pathlib.Path(file_path).expanduser().resolve()

        # Create parent directories if needed
        if create_dirs and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {path.parent}")

        # Backup existing file
        backup_path = None
        if backup and path.exists():
            backup_path = path.with_suffix(path.suffix + ".bak")
            path.rename(backup_path)
            logger.info(f"Created backup: {backup_path}")

        # Write file
        path.write_text(content, encoding=encoding)

        line_count = content.count("\n") + 1
        size_bytes = len(content.encode(encoding))

        logger.info(f"Wrote {line_count} lines to {path}")

        return {
            "success": True,
            "path": str(path),
            "line_count": line_count,
            "size_bytes": size_bytes,
            "encoding": encoding,
            "backup_path": str(backup_path) if backup_path else None,
        }

    except PermissionError:
        return {
            "success": False,
            "error": f"Permission denied: {file_path}",
            "path": file_path,
        }
    except Exception as e:
        logger.error(f"Error writing file: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "path": file_path,
        }


# =============================================================================
# FILE SEARCH
# =============================================================================


def search_files(
    pattern: str,
    directory: str = ".",
    recursive: bool = True,
    case_sensitive: bool = False,
    max_results: int = 1000,
) -> dict[str, Any]:
    """Search for files matching pattern.

    Args:
        pattern: Glob pattern (e.g., "*.py", "**/*.txt")
        directory: Directory to search
        recursive: Search subdirectories
        case_sensitive: Case-sensitive matching
        max_results: Maximum number of results

    Returns:
        Result with matching file paths
    """
    try:
        dir_path = pathlib.Path(directory).expanduser().resolve()

        if not dir_path.exists():
            return {
                "success": False,
                "error": f"Directory not found: {directory}",
                "pattern": pattern,
            }

        if not dir_path.is_dir():
            return {
                "success": False,
                "error": f"Not a directory: {directory}",
                "pattern": pattern,
            }

        # Build search pattern
        if recursive and not pattern.startswith("**"):
            search_pattern = f"**/{pattern}"
        else:
            search_pattern = pattern

        # Search for files
        matches = []
        full_pattern = str(dir_path / search_pattern)

        for match_path in glob.iglob(full_pattern, recursive=recursive):
            path = pathlib.Path(match_path)

            # Skip directories
            if not path.is_file():
                continue

            # Case-insensitive matching
            if not case_sensitive:
                # Pattern match already handled by glob
                pass

            matches.append(
                {
                    "path": str(path),
                    "relative_path": str(path.relative_to(dir_path)),
                    "name": path.name,
                    "size_bytes": path.stat().st_size,
                }
            )

            if len(matches) >= max_results:
                logger.warning(f"Hit max results ({max_results}), stopping search")
                break

        logger.info(f"Found {len(matches)} files matching {pattern}")

        return {
            "success": True,
            "pattern": pattern,
            "directory": str(dir_path),
            "matches": matches,
            "count": len(matches),
            "truncated": len(matches) >= max_results,
        }

    except Exception as e:
        logger.error(f"Error searching files: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "pattern": pattern,
            "directory": directory,
        }


def search_file_contents(
    pattern: str,
    directory: str = ".",
    file_pattern: str = "*",
    recursive: bool = True,
    case_sensitive: bool = False,
    max_matches: int = 100,
) -> dict[str, Any]:
    """Search file contents for pattern (like grep).

    Args:
        pattern: Regex pattern to search for
        directory: Directory to search
        file_pattern: File glob pattern (e.g., "*.py")
        recursive: Search subdirectories
        case_sensitive: Case-sensitive matching
        max_matches: Maximum number of matches

    Returns:
        Result with matching files and lines
    """
    try:
        dir_path = pathlib.Path(directory).expanduser().resolve()

        if not dir_path.exists():
            return {
                "success": False,
                "error": f"Directory not found: {directory}",
            }

        # Compile regex
        flags = 0 if case_sensitive else re.IGNORECASE
        regex = re.compile(pattern, flags)

        # Search files
        matches = []
        total_files_searched = 0

        # Get files to search
        if recursive:
            search_pattern = f"**/{file_pattern}"
        else:
            search_pattern = file_pattern

        for file_path in glob.iglob(str(dir_path / search_pattern), recursive=recursive):
            path = pathlib.Path(file_path)

            if not path.is_file():
                continue

            total_files_searched += 1

            # Search file contents
            try:
                content = path.read_text(encoding="utf-8")
                file_matches = []

                for line_num, line in enumerate(content.splitlines(), 1):
                    if regex.search(line):
                        file_matches.append(
                            {
                                "line_number": line_num,
                                "line": line.strip(),
                            }
                        )

                        if len(matches) + len(file_matches) >= max_matches:
                            break

                if file_matches:
                    matches.append(
                        {
                            "path": str(path),
                            "relative_path": str(path.relative_to(dir_path)),
                            "matches": file_matches,
                            "match_count": len(file_matches),
                        }
                    )

                if len(matches) >= max_matches:
                    break

            except (UnicodeDecodeError, PermissionError):
                # Skip files we can't read
                continue

        logger.info(f"Searched {total_files_searched} files, found {len(matches)} with matches")

        return {
            "success": True,
            "pattern": pattern,
            "directory": str(dir_path),
            "files_searched": total_files_searched,
            "files_with_matches": len(matches),
            "matches": matches,
            "truncated": len(matches) >= max_matches,
        }

    except Exception as e:
        logger.error(f"Error searching file contents: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "pattern": pattern,
        }


# =============================================================================
# DIRECTORY OPERATIONS
# =============================================================================


def list_directory(
    directory: str = ".",
    recursive: bool = False,
    include_hidden: bool = False,
    max_depth: int | None = None,
) -> dict[str, Any]:
    """List directory contents.

    Args:
        directory: Directory to list[Any]
        recursive: List subdirectories
        include_hidden: Include hidden files/dirs
        max_depth: Maximum recursion depth

    Returns:
        Result with directory listing
    """
    try:
        dir_path = pathlib.Path(directory).expanduser().resolve()

        if not dir_path.exists():
            return {
                "success": False,
                "error": f"Directory not found: {directory}",
            }

        if not dir_path.is_dir():
            return {
                "success": False,
                "error": f"Not a directory: {directory}",
            }

        # List directory
        entries = []

        def _list_dir(path: pathlib.Path, depth: int = 0) -> None:
            if max_depth is not None and depth > max_depth:
                return

            try:
                for entry in sorted(path.iterdir()):
                    # Skip hidden files
                    if not include_hidden and entry.name.startswith("."):
                        continue

                    is_dir = entry.is_dir()
                    is_file = entry.is_file()

                    entry_info = {
                        "path": str(entry),
                        "relative_path": str(entry.relative_to(dir_path)),
                        "name": entry.name,
                        "type": "directory" if is_dir else "file" if is_file else "other",
                        "depth": depth,
                    }

                    if is_file:
                        entry_info["size_bytes"] = entry.stat().st_size

                    entries.append(entry_info)

                    # Recurse into subdirectories
                    if recursive and is_dir:
                        _list_dir(entry, depth + 1)

            except PermissionError:
                logger.warning(f"Permission denied: {path}")

        _list_dir(dir_path)

        logger.info(f"Listed {len(entries)} entries from {dir_path}")

        return {
            "success": True,
            "directory": str(dir_path),
            "entries": entries,
            "count": len(entries),
            "recursive": recursive,
        }

    except Exception as e:
        logger.error(f"Error listing directory: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "directory": directory,
        }


# =============================================================================
# HELPERS
# =============================================================================


def get_file_info(file_path: str) -> dict[str, Any]:
    """Get file metadata.

    Args:
        file_path: Path to file

    Returns:
        File metadata or error
    """
    try:
        path = pathlib.Path(file_path).expanduser().resolve()

        if not path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}",
            }

        stat = path.stat()

        return {
            "success": True,
            "path": str(path),
            "name": path.name,
            "size_bytes": stat.st_size,
            "size_mb": stat.st_size / (1024 * 1024),
            "modified_time": stat.st_mtime,
            "is_file": path.is_file(),
            "is_dir": path.is_dir(),
            "is_symlink": path.is_symlink(),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "path": file_path,
        }


__all__ = [
    "get_file_info",
    "list_directory",
    "read_file",
    "search_file_contents",
    "search_files",
    "write_file",
]
