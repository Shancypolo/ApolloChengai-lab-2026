import csv
import io
import sys


def clean_header(header):
    # Make column names match even if they have extra spaces,
    # different capital letters, or a hidden BOM character.
    return header.strip().lstrip("\ufeff").casefold()


def get_delimiter(text):
    # Excel files may use commas, semicolons, tabs, or pipes.
    # Try to detect which one is being used.
    try:
        return csv.Sniffer().sniff(text[:4096], delimiters=",;\t|").delimiter
    except csv.Error:
        # If we can't tell, assume a normal comma-separated file.
        return ","


def open_csv(filename):
    # Some files are saved in different text encodings.
    # Try the most common ones until one works.
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            with open(filename, "r", encoding=encoding, newline="") as file:
                text = file.read()
            return text
        except UnicodeDecodeError:
            continue

    # If nothing works, try one more time and let Python show the error.
    with open(filename, "r", encoding="utf-8-sig", newline="") as file:
        return file.read()


def number_from_text(text):
    # Ignore empty cells and text that is not a number.
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None

    # Remove things like commas, dollar signs, and percent signs.
    # Example: "95%" becomes "95".
    text = text.replace(",", "").replace("$", "").replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def read_scores(filename, warnings):
    # First, read the whole file so we can figure out how it is separated.
    text = open_csv(filename)
    delimiter = get_delimiter(text)

    # Use the detected separator to read the file as rows and columns.
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    # Keep the original header names, but also make a cleaned version
    # so names like " Name " and "name" match the same column.
    original_headers = reader.fieldnames or []
    headers = {}
    for header in original_headers:
        if header:
            headers[clean_header(header)] = header

    name_header = headers.get("name")
    if name_header is None:
        warnings.append(filename + ": skipped file because it has no name column.")
        return

    # These are common names for score columns.
    # We do not want to count things like student ID, ZIP code, or homeroom.
    score_names = {
        "grade", "grades", "score", "scores", "mark", "marks",
        "math", "science", "english", "reading", "writing",
        "history", "test", "exam",
    }
    metadata_names = {
        "year", "homeroom", "student id", "student_id", "id",
        "zip", "zipcode", "zip code",
    }

    # Pick the columns that look like grades.
    score_headers = []
    for cleaned, original in headers.items():
        if cleaned in score_names:
            score_headers.append(original)

    # If there are no obvious grade names, use the remaining numeric columns.
    if not score_headers:
        for cleaned, original in headers.items():
            if cleaned != "name" and cleaned not in metadata_names:
                score_headers.append(original)

    if not score_headers:
        warnings.append(filename + ": skipped file because it has no score columns.")
        return

    # Tell the user which columns were ignored.
    for cleaned, original in headers.items():
        if original != name_header and original not in score_headers:
            warnings.append(filename + ": skipped column '" + original + "'.")

    for line_number, row in enumerate(reader, start=2):
        # If the row has extra values, warn the user.
        if None in row:
            warnings.append(
                filename + ", line " + str(line_number)
                + ": skipped extra values after the expected columns."
            )

        # Ignore empty names and remove extra spaces.
        name = (row.get(name_header) or "").strip()
        if not name:
            warnings.append(
                filename + ", line " + str(line_number)
                + ": skipped row because the name is blank."
            )
            continue

        scores = []
        bad_score = False
        for header in score_headers:
            score = number_from_text(row.get(header))
            if score is None:
                # If a row is missing a score, skip that entire row.
                # This prevents a bad grade from hurting the average.
                bad_score = True
                warnings.append(
                    filename + ", line " + str(line_number)
                    + ": skipped row for " + name
                    + " because column '" + header + "' is blank or invalid."
                )
                break
            scores.append(score)

        # Only keep rows that have real, complete scores.
        if scores and not bad_score:
            yield name, sum(scores) / len(scores)


def main():
    # The user can give one or more file names when running the script.
    if len(sys.argv) < 2:
        print("Warnings:")
        print("- No CSV files were supplied.")
        print()
        print("Top scoring students:")
        print("No valid student scores found.")
        return

    # Store each student's scores together.
    # We use lowercase names so "BOB SMITH" and "Bob Smith" are treated as the same student.
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
            # If one file is broken, keep going and warn the user.
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

    # Each student may have many rows. Average all of their scores together.
    student_averages = {}
    for identity, scores in scores_by_student.items():
        student_averages[identity] = sum(scores) / len(scores)

    highest_average = max(student_averages.values())
    top_students = []
    for identity, average in student_averages.items():
        # If students tie for the highest average, show all of them.
        if average == highest_average:
            top_students.append(display_names[identity])

    print("Top scoring students:")
    for name in top_students:
        print(name)


if __name__ == "__main__":
    main()
