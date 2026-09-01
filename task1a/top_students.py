import csv
import io
import sys


def clean_header(header):
    # Remove spaces, BOM, and make names case-insensitive so
    # " Name " and "name" match the same column.
    if header is None:
        return ""
    return str(header).strip().lstrip("\ufeff").casefold()


def get_delimiter(text):
    # Excel CSV files often use commas, semicolons, tabs, or pipes.
    # Try the normal CSV sniffing first, then fall back to simple checks.
    try:
        return csv.Sniffer().sniff(text[:4096], delimiters=",;\t|").delimiter
    except csv.Error:
        if ";" in text and "," not in text:
            return ";"
        if "\t" in text and "," not in text:
            return "\t"
        if "|" in text and "," not in text:
            return "|"
        return ","


def open_csv(filename):
    # Excel files may use UTF-8, UTF-16, or Windows encoding.
    # Try common encodings and keep going until one works.
    for encoding in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            with open(filename, "r", encoding=encoding, newline="") as file:
                return file.read()
        except UnicodeDecodeError:
            continue

    # If all encodings fail, then let Python raise the real error.
    with open(filename, "r", encoding="utf-8-sig", newline="") as file:
        return file.read()


def number_from_text(value):
    # Ignore empty cells and text that is not a number.
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    # Remove common number formatting like commas, $ and %.
    cleaned = text.replace(",", "").replace("$", "").replace("%", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def read_scores(filename, warnings):
    # Read the entire file as text first so we can detect file type.
    text = open_csv(filename)
    if not text.strip():
        warnings.append(filename + ": skipped file because it is empty.")
        return

    delimiter = get_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    original_headers = reader.fieldnames or []
    headers = {}
    for header in original_headers:
        clean_name = clean_header(header)
        if clean_name:
            headers[clean_name] = header

    name_header = headers.get("name")
    if name_header is None:
        warnings.append(filename + ": skipped file because it has no name column.")
        return

    # Common grade names and values that should be ignored as metadata.
    score_names = {
        "grade", "grades", "score", "scores", "mark", "marks",
        "math", "science", "english", "reading", "writing",
        "history", "test", "exam",
    }
    metadata_names = {
        "year", "homeroom", "student id", "student_id", "id",
        "zip", "zipcode", "zip code",
    }

    score_headers = []
    for cleaned_name, original_name in headers.items():
        if cleaned_name in score_names:
            score_headers.append(original_name)

    # If no obvious grade names are found, use all remaining numeric columns.
    if not score_headers:
        for cleaned_name, original_name in headers.items():
            if cleaned_name != "name" and cleaned_name not in metadata_names:
                score_headers.append(original_name)

    if not score_headers:
        warnings.append(filename + ": skipped file because it has no score columns.")
        return

    # Warn about columns that were skipped because they do not look like score data.
    for cleaned_name, original_name in headers.items():
        if original_name != name_header and original_name not in score_headers:
            warnings.append(filename + ": skipped column '" + original_name + "'.")

    for line_number, row in enumerate(reader, start=2):
        # Extra values usually means the CSV row had too many cells.
        if None in row:
            warnings.append(
                filename + ", line " + str(line_number)
                + ": skipped extra values after the expected columns."
            )

        row_name = (row.get(name_header) or "").strip()
        if not row_name:
            warnings.append(
                filename + ", row " + str(line_number)
                + ": skipped row because cell in column '" + name_header + "' is blank."
            )
            continue

        scores = []
        bad_row = False
        for header in score_headers:
            cell_value = row.get(header)
            score = number_from_text(cell_value)
            if score is None:
                bad_row = True
                warnings.append(
                    filename + ", row " + str(line_number)
                    + ", column '" + header + "', cell '" + str(cell_value) + "'"
                    + ": skipped row because score is blank or invalid."
                )
                break
            scores.append(score)

        if scores and not bad_row:
            yield row_name, sum(scores) / len(scores)


def main():
    # The script can accept one or more CSV files when the user runs it.
    if len(sys.argv) < 2:
        print("Warnings:")
        print("- No CSV files were supplied.")
        print()
        print("Top scoring students:")
        print("No valid student scores found.")
        return

    scores_by_student = {}
    display_names = {}
    warnings = []

    for filename in sys.argv[1:]:
        try:
            records = read_scores(filename, warnings)
            for name, average in records:
                identity = " ".join(name.casefold().split())
                scores_by_student.setdefault(identity, []).append(average)
                display_names.setdefault(identity, name)
        except (OSError, UnicodeError, csv.Error) as error:
            warnings.append(filename + ": skipped file (" + str(error) + ").")

    print("Warnings:")
    if warnings:
        for warning in warnings:
            print("- " + warning)
    else:
        print("- None")
    print()

    if not scores_by_student:
        print("Top scoring students:")
        print("No valid student scores found.")
        return

    student_averages = {}
    for identity, scores in scores_by_student.items():
        student_averages[identity] = sum(scores) / len(scores)

    highest_average = max(student_averages.values())
    top_students = []
    for identity, average in student_averages.items():
        if average == highest_average:
            top_students.append(display_names[identity])

    print("Top scoring students:")
    for name in top_students:
        print(name)


if __name__ == "__main__":
    main()
