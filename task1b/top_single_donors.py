import csv
import io
import sys


def clean_name(value):
    # Make names easier to compare.
    # Example: "  ANONYMOUS  " becomes "anonymous".
    if value is None:
        return ""
    text = str(value).strip().lstrip("\ufeff")
    text = " ".join(text.split())
    return text.casefold()


def normalize_donor_name(value):
    # Treat anonymous as one person, even if it appears many times.
    name = clean_name(value)
    if name == "anonymous":
        return "anonymous"
    return name


def detect_delimiter(text):
    # Excel files often use commas, semicolons, tabs, or pipes.
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
    # Try common encodings that Excel often uses.
    encodings = ("utf-8-sig", "utf-16", "cp1252", "latin-1")
    for encoding in encodings:
        try:
            with open(filename, "r", encoding=encoding, newline="") as file:
                return file.read()
        except UnicodeDecodeError:
            continue

    # If all encodings fail, let Python show the real error.
    with open(filename, "r", encoding="utf-8-sig", newline="") as file:
        return file.read()


def to_number(value):
    # Turn a text cell like "$12,50" or "50" into a float.
    if value is None:
        return None

    text = str(value).strip()
    if text == "":
        return None

    text = text.replace(",", "").replace("$", "").replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def read_donations(filename, warnings):
    # Read the file as text first so we can detect CSV format.
    text = open_csv(filename)
    if not text.strip():
        warnings.append(filename + ": skipped file because it is empty.")
        return []

    delimiter = detect_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    # Match common column name variations.
    fieldnames = reader.fieldnames or []
    headers = {}
    for heading in fieldnames:
        if heading is None:
            continue
        clean = clean_name(heading)
        if clean:
            headers[clean] = heading

    donor_header = None
    value_header = None
    for key, original in headers.items():
        if key in ("donor_name", "donorname", "donor"):
            donor_header = original
        if key in ("estimated_value", "estimatedvalue", "value", "amount"):
            value_header = original

    if donor_header is None or value_header is None:
        warnings.append(filename + ": skipped file because it does not have donor name and estimated value columns.")
        return []

    rows = []
    for row_number, row in enumerate(reader, start=2):
        donor_name = (row.get(donor_header) or "").strip()
        if donor_name == "":
            warnings.append(
                filename + ", row " + str(row_number)
                + ", column '" + donor_header + "', cell '" + str(row.get(donor_header)) + "'"
                + ": skipped row because donor name is blank."
            )
            continue

        raw_value = row.get(value_header)
        value = to_number(raw_value)
        if value is None:
            warnings.append(
                filename + ", row " + str(row_number)
                + ", column '" + value_header + "', cell '" + str(raw_value) + "'"
                + ": skipped row because estimated value is blank or invalid."
            )
            continue

        # A value of 0 is still a real donation, not a missing value.
        # We accept it and keep it in the ranking.

        name_key = normalize_donor_name(donor_name)
        rows.append((name_key, donor_name, value, row_number))

    return rows


def main():
    # The user can run the script with one or more CSV files.
    if len(sys.argv) < 2:
        print("Warnings:")
        print("- No CSV files were supplied.")
        print()
        print("Top 5 single-time donors:")
        print("No single-time donors found.")
        return

    warnings = []
    top_values = {}
    display_names = {}

    for filename in sys.argv[1:]:
        try:
            rows = read_donations(filename, warnings)
            for name_key, donor_name, value, row_number in rows:
                # Keep the biggest donation for each person.
                if name_key not in display_names:
                    display_names[name_key] = donor_name

                if name_key not in top_values:
                    top_values[name_key] = value
                elif value > top_values[name_key]:
                    top_values[name_key] = value
        except (OSError, UnicodeError, csv.Error) as error:
            warnings.append(filename + ": skipped file (" + str(error) + ").")

    # Turn each donor into one value: their largest donation.
    ranked_donors = []
    for name_key, value in top_values.items():
        ranked_donors.append((value, display_names[name_key]))

    # Sort biggest donation first.
    ranked_donors.sort(key=lambda item: item[0], reverse=True)

    print("Warnings:")
    if warnings:
        for warning in warnings:
            print("- " + warning)
    else:
        print("- None")
    print()

    if not ranked_donors:
        print("Top 5 donors by biggest single donation:")
        print("No valid donors found.")
        return

    # Show the top 5, but include all ties at the cutoff.
    top_five = ranked_donors[:5]
    cutoff_value = top_five[-1][0]
    final_list = [item for item in ranked_donors if item[0] >= cutoff_value]

    print("Top 5 donors by biggest single donation:")
    for value, donor_name in final_list:
        print(donor_name + " - " + format(value, ".2f"))


if __name__ == "__main__":
    main()
