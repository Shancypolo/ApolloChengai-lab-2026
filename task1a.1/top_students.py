import csv
import io
import sys


def clean_header(header):
    # Spaces, capital letters, and a BOM can make the same header
    # look different to a program.
    return header.strip().lstrip("\ufeff").casefold()


def get_delimiter(text):
    # Excel can save a table with commas, semicolons, or tabs.
    # Sniffer checks the header and sample rows to guess the separator.
    try:
        return csv.Sniffer().sniff(text[:4096], delimiters=",;\t|").delimiter
    except csv.Error:
        # A normal comma CSV is the safest fallback when guessing fails.
        return ","


def open_csv(filename):
    # utf-8-sig removes an optional UTF-8 BOM added by Excel.
    # utf-16 and cp1252 cover other common Windows/Excel exports.
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            with open(filename, "r", encoding=encoding, newline="") as file:
                text = file.read()
            return text
        except UnicodeDecodeError:
            continue

    # If none of the usual encodings worked, show the real file error.
    with open(filename, "r", encoding="utf-8-sig", newline="") as file:
        return file.read()


def number_from_text(text):
    # Empty cells, spaces, and text such as "eighty-eight" are not scores.
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None

    # Excel may export numbers with a percent sign, currency sign,
    # or thousands separators. A score of "95%" remains the score 95.
    text = text.replace(",", "").replace("$", "").replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def read_scores(filename, warnings):
    # Read the complete text first so delimiter detection works.
    text = open_csv(filename)
    delimiter = get_delimiter(text)
    # StringIO keeps quoted commas and quoted line breaks inside one cell.
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    # Keep original headers for row lookup, but compare cleaned headers.
    original_headers = reader.fieldnames or []
    headers = {}
    for header in original_headers:
        if header:
            headers[clean_header(header)] = header

    name_header = headers.get("name")
    if name_header is None:
        warnings.append(filename + ": skipped file because it has no name column.")
        return

    # These are common score names. They help us avoid averaging numeric
    # metadata such as homeroom, year, student ID, or ZIP code.
    score_names = {
        "grade", "grades", "score", "scores", "mark", "marks",
        "math", "science", "english", "reading", "writing",
        "history", "test", "exam",
    }
    metadata_names = {
        "year", "homeroom", "student id", "student_id", "id",
        "zip", "zipcode", "zip code",
    }

    # Prefer a single grade/score column when one exists.
    score_headers = []
    for cleaned, original in headers.items():
        if cleaned in score_names:
            score_headers.append(original)

    # If there is no obvious score header, use numeric-looking columns,
    # except columns whose names clearly describe metadata.
    if not score_headers:
        for cleaned, original in headers.items():
            if cleaned != "name" and cleaned not in metadata_names:
                score_headers.append(original)

    if not score_headers:
        warnings.append(filename + ": skipped file because it has no score columns.")
        return

    # Tell the user which columns were not used, rather than silently
    # pretending every column in the file was a grade.
    for cleaned, original in headers.items():
        if original != name_header and original not in score_headers:
            warnings.append(filename + ": skipped column '" + original + "'.")

    for line_number, row in enumerate(reader, start=2):
        # DictReader stores extra values under the special None key.
        if None in row:
            warnings.append(
                filename + ", line " + str(line_number)
                + ": skipped extra values after the expected columns."
            )

        # Ignore blank names and remove accidental spaces around names.
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
                # Do not give a student a partial average when one subject
                # is blank or invalid; skip the incomplete row instead.
                bad_score = True
                warnings.append(
                    filename + ", line " + str(line_number)
                    + ": skipped row for " + name
                    + " because column '" + header + "' is blank or invalid."
                )
                break
            scores.append(score)

        # A row needs at least one score, and every selected score must be
        # valid, so incomplete records cannot unfairly change an average.
        if scores and not bad_score:
            yield name, sum(scores) / len(scores)


def main():
    # Accept one or more CSV paths from the command line.
    if len(sys.argv) < 2:
        print("Warnings:")
        print("- No CSV files were supplied.")
        print()
        print("Top scoring students:")
        print("No valid student scores found.")
        return

    # Store all records by lowercase name so capitalization differences
    # such as "BOB SMITH" and "Bob Smith" become one student.
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
            # One bad file should not prevent the other input files from
            # being processed and reported.
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

    # Repeated rows represent more grades for the same student, so average
    # those row averages before finding the highest student average.
    student_averages = {}
    for identity, scores in scores_by_student.items():
        student_averages[identity] = sum(scores) / len(scores)

    highest_average = max(student_averages.values())
    top_students = []
    for identity, average in student_averages.items():
        # Keep every student tied for first place.
        if average == highest_average:
            top_students.append(display_names[identity])

    print("Top scoring students:")
    for name in top_students:
        print(name)


if __name__ == "__main__":
    main()
