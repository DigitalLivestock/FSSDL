import glob
import json
import logging
import os
import subprocess
import sys
from typing import Any

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend — safe for server use
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from mcp.server.fastmcp import FastMCP

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
log = logging.getLogger("fssdl-mcp")

mcp = FastMCP("FSSDL")

# Active logging subprocess (only one session at a time)
_logging_process: subprocess.Popen | None = None


# ---------------------------------------------------------------------------
# Log file tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_log_files(directory: str = ".") -> list[str]:
    """List all .log and .csv data files in the given directory."""
    directory = os.path.abspath(directory)
    files = glob.glob(os.path.join(directory, "*.log")) + glob.glob(os.path.join(directory, "*.csv"))
    return sorted(files)


@mcp.tool()
def get_log_summary(file_path: str) -> dict[str, Any]:
    """Return a summary of a FSSDL log file: row count, time range, and column count."""
    df = pd.read_csv(file_path, header=None)
    if df.empty:
        return {"rows": 0, "columns": 0, "first_timestamp": None, "last_timestamp": None}
    timestamps = pd.to_datetime(df.iloc[:, 0], errors="coerce")
    return {
        "rows": len(df),
        "data_columns": df.shape[1] - 1,
        "first_timestamp": str(timestamps.iloc[0]) if not timestamps.empty else None,
        "last_timestamp": str(timestamps.iloc[-1]) if not timestamps.empty else None,
    }


@mcp.tool()
def read_log_data(file_path: str, limit: int = 100) -> list[dict[str, Any]]:
    """Return the last `limit` rows of a FSSDL log file as a list of records.

    Each record has a 'timestamp' key plus one key per data column ('col_1', 'col_2', ...).
    """
    df = pd.read_csv(file_path, header=None)
    if df.empty:
        return []
    cols = ["timestamp"] + [f"col_{i}" for i in range(1, df.shape[1])]
    df.columns = cols
    return df.tail(limit).to_dict("records")


# ---------------------------------------------------------------------------
# Column config tools
# ---------------------------------------------------------------------------

@mcp.tool()
def read_column_config(config_path: str) -> dict[str, Any]:
    """Read a FSSDL column names config JSON file and return its contents."""
    with open(config_path, "r") as f:
        return json.load(f)


@mcp.tool()
def write_column_config(config_path: str, columns: list[str]) -> str:
    """Write a FSSDL column names config JSON file with the provided column names."""
    with open(config_path, "w") as f:
        json.dump({"columns": columns}, f, indent=4)
    return f"Written to {config_path}"


# ---------------------------------------------------------------------------
# Logging session tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_logging_status() -> dict[str, Any]:
    """Return the current status of the active logging session."""
    global _logging_process
    if _logging_process is None:
        return {"running": False, "pid": None}
    if _logging_process.poll() is not None:
        _logging_process = None
        return {"running": False, "pid": None}
    return {"running": True, "pid": _logging_process.pid}


@mcp.tool()
def start_logging(
    port: str,
    baudrate: int,
    output: str,
    separator: str = ",",
    end: str = "\n",
) -> dict[str, Any]:
    """Start a FSSDL logging session on the given serial port.

    Args:
        port: Serial port (e.g. COM3 or /dev/ttyUSB0)
        baudrate: Baud rate (e.g. 9600)
        output: Output file path for the log
        separator: Field separator character (default: ',')
        end: Line end character (default: newline)
    """
    global _logging_process
    if _logging_process is not None and _logging_process.poll() is None:
        return {"started": False, "reason": "A logging session is already running.", "pid": _logging_process.pid}

    server_dir = os.path.dirname(os.path.abspath(__file__))
    main_py = os.path.join(server_dir, "main.py")

    _logging_process = subprocess.Popen(
        [sys.executable, main_py, port, str(baudrate), output, "--separator", separator, "--end", end],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    log.info("Started logging session PID=%d → %s", _logging_process.pid, output)
    return {"started": True, "pid": _logging_process.pid, "output": output}


@mcp.tool()
def stop_logging() -> dict[str, Any]:
    """Stop the active FSSDL logging session."""
    global _logging_process
    if _logging_process is None or _logging_process.poll() is not None:
        _logging_process = None
        return {"stopped": False, "reason": "No active logging session."}

    pid = _logging_process.pid
    _logging_process.terminate()
    try:
        _logging_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _logging_process.kill()
    _logging_process = None
    log.info("Stopped logging session PID=%d", pid)
    return {"stopped": True, "pid": pid}


# ---------------------------------------------------------------------------
# Plot tool
# ---------------------------------------------------------------------------

@mcp.tool()
def generate_plot(data_file: str, column_config: str, output_path: str) -> str:
    """Generate a time-series PNG plot from a FSSDL log file.

    Args:
        data_file: Path to the FSSDL CSV log file
        column_config: Path to the JSON column names config file
        output_path: Path where the PNG image will be saved
    """
    with open(column_config, "r") as f:
        config = json.load(f)
    columns: list[str] = config["columns"]

    df = pd.read_csv(data_file, header=None)

    n_data_cols = df.shape[1] - 1
    if len(columns) != n_data_cols:
        raise ValueError(
            f"Config has {len(columns)} column name(s) but data has {n_data_cols} data column(s)."
        )

    df.columns = ["timestamp"] + columns
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    for col in columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    fig, ax = plt.subplots(figsize=(12, 5))
    for col in columns:
        ax.plot(df["timestamp"], df[col], label=col)

    ax.set_title(os.path.basename(data_file))
    ax.set_xlabel("Time")
    ax.set_ylabel("Value")
    ax.legend()
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    fig.autofmt_xdate()
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close(fig)
    log.info("Plot saved to %s", output_path)
    return os.path.abspath(output_path)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
