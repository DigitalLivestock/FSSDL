import argparse
import json
import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot FSSDL captured data")
    parser.add_argument("data_file", type=str, help="Path to the FSSDL CSV data file")
    parser.add_argument("column_config", type=str, help="Path to JSON file with column names")
    args = parser.parse_args()

    # Load column config
    try:
        with open(args.column_config, "r") as f:
            config = json.load(f)
        columns = config["columns"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
        print(f"[ERROR] Failed to load column config: {e}", file=sys.stderr)
        sys.exit(1)

    # Load data
    try:
        df = pd.read_csv(args.data_file, header=None)
    except FileNotFoundError:
        print(f"[ERROR] Data file not found: {args.data_file}", file=sys.stderr)
        sys.exit(1)

    n_data_cols = df.shape[1] - 1  # subtract timestamp column
    if len(columns) != n_data_cols:
        print(
            f"[ERROR] Config has {len(columns)} column name(s) but data has {n_data_cols} data column(s).",
            file=sys.stderr,
        )
        sys.exit(1)

    # Parse timestamp
    df.columns = ["timestamp"] + columns
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Convert data columns to numeric
    for col in columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Plot
    fig, ax = plt.subplots(figsize=(12, 5))

    for col in columns:
        ax.plot(df["timestamp"], df[col], label=col)

    ax.set_title(args.data_file)
    ax.set_xlabel("Time")
    ax.set_ylabel("Value")
    ax.legend()
    ax.grid(True, linestyle="--", alpha=0.5)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    fig.autofmt_xdate()

    plt.tight_layout()
    plt.show()
