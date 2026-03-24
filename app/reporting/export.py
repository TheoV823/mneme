import csv
import json
import io


def export_csv(unblinded):
    output = io.StringIO()
    if not unblinded:
        return ""
    fieldnames = ["user_id", "prompt_text", "prompt_category",
                  "closeness_a", "closeness_b", "closeness_delta", "true_winner_closeness",
                  "usefulness_a", "usefulness_b", "usefulness_delta", "true_winner_usefulness",
                  "distinctiveness_a", "distinctiveness_b", "distinctiveness_delta", "true_winner_distinctiveness",
                  "preference", "true_preference", "notes"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in unblinded:
        writer.writerow(row)
    return output.getvalue()


def export_json(unblinded, report):
    return json.dumps({"report": report, "rows": unblinded}, indent=2, default=str)
