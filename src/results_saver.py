import json
import csv
from datetime import datetime
from typing import Dict, List
from pathlib import Path


class ResultsSaver:
    """Class to handle saving crawler results to various formats"""

    def __init__(self, output_dir: str = "results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Create timestamped session directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"session_{timestamp}"
        self.session_dir.mkdir(exist_ok=True)

        # File paths
        self.json_file = self.session_dir / "results.json"
        self.csv_file = self.session_dir / "results.csv"
        self.summary_file = self.session_dir / "summary.txt"

        # Initialize results storage
        self.results: List[Dict] = []
        self.stats = {
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
        }

    def add_result(self, result: Dict) -> None:
        """Add a single result to the collection"""
        if result:
            self.results.append(result)
            self.stats["successful"] += 1
        self.stats["total_processed"] += 1

    def save_json(self) -> None:
        """Save results to JSON file"""
        data = {
            "metadata": {
                "session_info": {
                    "start_time": self.stats["start_time"],
                    "end_time": datetime.now().isoformat(),
                    "total_results": len(self.results),
                },
                "statistics": self.stats,
            },
            "results": self.results,
        }

        with open(self.json_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save_csv(self) -> None:
        """Save results to CSV file with meaningful data columns only"""
        if not self.results:
            return

        # Define the exact column order for CSV (meaningful fields only)
        csv_columns = [
            "registration_number",
            "timestamp",
            "total_subjects",
            "source",
            "Id",
            "TinhId",
            "MA_MON_NGOAI_NGU",
            "SBD",
            "TONGDIEM",
            "TOAN",
            "VAN",
            "NGOAI_NGU",
            "SU",
            "DIA",
            "GDKT_PL",
            "LI",
            "HOA",
            "SINH",
            "TIN_HOC",
            "GIAO_DUC_CONG_DAN",
            "CN_CONG_NGHIEP",
            "CN_NONG_NGHIEP",
        ]

        with open(self.csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_columns)
            writer.writeheader()

            for result in self.results:
                row = {}

                # Copy all fields that exist in the result
                for field in csv_columns:
                    row[field] = result.get(field, "")

                # Format timestamp for readability
                if "timestamp" in result:
                    row["timestamp"] = datetime.fromtimestamp(
                        result["timestamp"]
                    ).strftime("%Y-%m-%d %H:%M:%S")

                writer.writerow(row)

    def save_summary(self) -> None:
        """Save summary statistics to text file"""
        self.stats["end_time"] = datetime.now().isoformat()
        self.stats["failed"] = self.stats["total_processed"] - self.stats["successful"]

        summary_content = f"""
THPT 2025 Crawler Results Summary
================================

Session Information:
- Start Time: {self.stats['start_time']}
- End Time: {self.stats['end_time']}
- Session Directory: {self.session_dir}

Statistics:
- Total Processed: {self.stats['total_processed']}
- Successful: {self.stats['successful']}
- Failed: {self.stats['failed']}
- Success Rate: {(self.stats['successful'] / max(1, self.stats['total_processed'])) * 100:.1f}%

Subject Analysis:
"""

        if self.results:
            # Analyze subjects
            all_subjects = set()
            subject_counts = {}

            for result in self.results:
                if "scores" in result:
                    for subject in result["scores"].keys():
                        all_subjects.add(subject)
                        subject_counts[subject] = subject_counts.get(subject, 0) + 1

            summary_content += f"- Unique Subjects Found: {len(all_subjects)}\n"
            summary_content += "- Most Common Subjects:\n"

            for subject, count in sorted(
                subject_counts.items(), key=lambda x: x[1], reverse=True
            )[:10]:
                summary_content += f"  * {subject}: {count} students\n"

            # Sample results
            summary_content += "\nSample Results (first 5):\n"
            for i, result in enumerate(self.results[:5]):
                summary_content += f"  {i+1}. {result['registration_number']}: "
                if "scores" in result:
                    total_score = result["scores"].get("Total Score", "N/A")
                    subject_count = len(
                        [s for s in result["scores"].keys() if s != "Total Score"]
                    )
                    summary_content += (
                        f"{subject_count} subjects, Total: {total_score}\n"
                    )
                else:
                    summary_content += "No scores\n"

        with open(self.summary_file, "w", encoding="utf-8") as f:
            f.write(summary_content)

    def save_all(self) -> None:
        """Save results in all formats"""
        self.save_json()
        self.save_csv()
        self.save_summary()

    def get_session_info(self) -> Dict:
        """Get information about the current session"""
        return {
            "session_dir": str(self.session_dir),
            "total_results": len(self.results),
            "files": {
                "json": str(self.json_file),
                "csv": str(self.csv_file),
                "summary": str(self.summary_file),
            },
            "stats": self.stats,
        }

    def print_summary(self) -> None:
        """Print a summary of results to console"""
        print(f"\n{'='*50}")
        print("CRAWLER RESULTS SUMMARY")
        print(f"{'='*50}")
        print(f"Session Directory: {self.session_dir}")
        print(f"Total Processed: {self.stats['total_processed']}")
        print(f"Successful: {self.stats['successful']}")
        print(f"Failed: {self.stats['failed']}")
        print(
            f"Success Rate: {(self.stats['successful'] / max(1, self.stats['total_processed'])) * 100:.1f}%"
        )

        if self.results:
            print("\nSample Results:")
            for i, result in enumerate(self.results[:5]):
                reg_num = result["registration_number"]
                if "scores" in result:
                    total_score = result["scores"].get("Total Score", "N/A")
                    subject_count = len(
                        [s for s in result["scores"].keys() if s != "Total Score"]
                    )
                    print(
                        f"  {i+1}. {reg_num}: {subject_count} subjects, Total: {total_score}"
                    )
                else:
                    print(f"  {i+1}. {reg_num}: No scores")

        print("\nFiles saved:")
        print(f"  - JSON: {self.json_file}")
        print(f"  - CSV: {self.csv_file}")
        print(f"  - Summary: {self.summary_file}")
        print(f"{'='*50}")
