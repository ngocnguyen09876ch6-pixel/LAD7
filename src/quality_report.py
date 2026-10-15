
from pathlib import Path
import json

import pandas as pd

from src.validators.schema_validator import (
    REQUIRED,
    REQUIRED_VALUES,
    validate_schema_and_completeness,
)
from src.validators.business_validator import split_valid_invalid
from src.validators.integrity_validator import split_cross_table_invalid


ROOT = Path(__file__).resolve().parent.parent

DIRTY_DIR = ROOT / "data" / "dirty" / "day_2026-07-02"
REPORT_DIR = ROOT / "reports"
EVIDENCE_DIR = ROOT / "docs" / "evidence"

INPUT_FILES = {
    "customers": "customers_daily.csv",
    "products": "products_daily.csv",
    "orders": "orders_daily.csv",
    "order_items": "order_items_daily.csv",
    "payments": "payments_daily.json",
}


def load_dirty_data():
    datasets = {}

    for name, filename in INPUT_FILES.items():
        file_path = DIRTY_DIR / filename

        if not file_path.exists():
            raise FileNotFoundError(
                f"Không tìm thấy file dữ liệu: {file_path}"
            )

        if file_path.suffix.lower() == ".json":
            df = pd.read_json(file_path)
        else:
            df = pd.read_csv(file_path)

        datasets[name] = df

        print(f"Loaded {name}: {len(df)} rows")

    return datasets


def run_schema_validation(datasets):
    results = {}

    for name, df in datasets.items():
        scored_df = validate_schema_and_completeness(
            df,
            REQUIRED[name],
            REQUIRED_VALUES[name],
        )

        schema_valid = scored_df[
            scored_df["score"] == 100
        ].copy()

        schema_invalid = scored_df[
            scored_df["score"] < 100
        ].copy()

        assert len(df) == (
            len(schema_valid) + len(schema_invalid)
        ), f"Schema invariant failed: {name}"

        results[name] = {
            "scored": scored_df,
            "valid": schema_valid,
            "invalid": schema_invalid,
        }

        print(
            f"[SCHEMA] {name}: "
            f"input={len(df)}, "
            f"valid={len(schema_valid)}, "
            f"rejected={len(schema_invalid)}"
        )

    return results


def run_business_validation(schema_results):
    results = {}

    for name, schema_result in schema_results.items():
        schema_valid = schema_result["valid"]

        business_valid, business_invalid = split_valid_invalid(
            name,
            schema_valid,
        )

        assert len(schema_valid) == (
            len(business_valid) + len(business_invalid)
        ), f"Business invariant failed: {name}"

        results[name] = {
            "schema_invalid": schema_result["invalid"],
            "business_valid": business_valid,
            "business_invalid": business_invalid,
        }

        print(
            f"[BUSINESS] {name}: "
            f"input={len(schema_valid)}, "
            f"valid={len(business_valid)}, "
            f"rejected={len(business_invalid)}"
        )

    return results


def run_integrity_validation(business_results):
    results = {}

    for name, business_result in business_results.items():
        business_valid = business_result["business_valid"]

        integrity_valid, integrity_invalid = (
            split_cross_table_invalid(
                name,
                business_valid,
            )
        )

        assert len(business_valid) == (
            len(integrity_valid) + len(integrity_invalid)
        ), f"Integrity invariant failed: {name}"

        results[name] = {
            "schema_invalid": business_result["schema_invalid"],
            "business_invalid": business_result["business_invalid"],
            "integrity_valid": integrity_valid,
            "integrity_invalid": integrity_invalid,
        }

        print(
            f"[INTEGRITY] {name}: "
            f"input={len(business_valid)}, "
            f"valid={len(integrity_valid)}, "
            f"rejected={len(integrity_invalid)}"
        )

        if (
            not integrity_invalid.empty
            and "error_code" in integrity_invalid.columns
        ):
            print("Integrity error counts:")
            print(
                integrity_invalid["error_code"]
                .value_counts()
                .to_string()
            )

    return results



def build_quality_report(datasets, integrity_results):
    report_rows = []

    invariant_lines = [
        "DATA QUALITY INVARIANT CHECK",
        "Invariant: input = valid + rejected",
        f"Source: data/dirty/{DIRTY_DIR.name}",
        "",
    ]

    for name, original_df in datasets.items():
        result = integrity_results[name]

        input_count = len(original_df)
        valid_count = len(result["integrity_valid"])

        schema_rejected = len(result["schema_invalid"])
        business_rejected = len(result["business_invalid"])
        integrity_rejected = len(result["integrity_invalid"])

        rejected_count = (
            schema_rejected
            + business_rejected
            + integrity_rejected
        )

        assert input_count == valid_count + rejected_count, (
            f"Invariant failed for {name}: "
            f"{input_count} != {valid_count} + {rejected_count}"
        )

        report_rows.append({
            "dataset": name,
            "input": input_count,
            "valid": valid_count,
            "rejected": rejected_count,
        })

        invariant_lines.append(
            f"{name}: {input_count} = "
            f"{valid_count} + {rejected_count} | PASS"
        )

        invariant_lines.append(
            f"  Breakdown: schema={schema_rejected}, "
            f"business={business_rejected}, "
            f"integrity={integrity_rejected}"
        )

    report_df = pd.DataFrame(
        report_rows,
        columns=["dataset", "input", "valid", "rejected"],
    )

    total_input = int(report_df["input"].sum())
    total_valid = int(report_df["valid"].sum())
    total_rejected = int(report_df["rejected"].sum())

    assert total_input == total_valid + total_rejected, (
        f"Total invariant failed: "
        f"{total_input} != {total_valid} + {total_rejected}"
    )

    invariant_lines.extend([
        "",
        f"TOTAL: {total_input} = "
        f"{total_valid} + {total_rejected} | PASS",
        "ALL INVARIANT CHECKS PASSED",
    ])

    summary = {
        "source_directory": f"data/dirty/{DIRTY_DIR.name}",
        "total": {
            "input": total_input,
            "valid": total_valid,
            "rejected": total_rejected,
        },
        "datasets": report_rows,
    }

    return report_df, summary, invariant_lines



def save_quality_report(report_df, summary, invariant_lines):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = REPORT_DIR / "data_quality_report.csv"
    report_df.to_csv(
        csv_path,
        index=False,
        encoding="utf-8-sig",
    )

    json_path = REPORT_DIR / "data_quality_summary.json"

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(
            summary,
            file,
            indent=2,
            ensure_ascii=False,
        )

    evidence_path = EVIDENCE_DIR / "07-invariant.txt"
    evidence_path.write_text(
        "\n".join(invariant_lines) + "\n",
        encoding="utf-8",
    )

    print("\n=== DATA QUALITY REPORT ===")
    print(report_df.to_string(index=False))

    print("\n=== TOTAL ===")
    print(f"Input:    {summary['total']['input']}")
    print(f"Valid:    {summary['total']['valid']}")
    print(f"Rejected: {summary['total']['rejected']}")

    print("\nSaved reports:")
    print(csv_path)
    print(json_path)
    print(evidence_path)



def main():
    datasets = load_dirty_data()
    schema_results = run_schema_validation(datasets)
    business_results = run_business_validation(schema_results)
    integrity_results = run_integrity_validation(business_results)

    report_df, summary, invariant_lines = build_quality_report(
        datasets,
        integrity_results,
    )

    save_quality_report(
        report_df,
        summary,
        invariant_lines,
    )


if __name__ == "__main__":
    main()
