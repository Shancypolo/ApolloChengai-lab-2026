import csv
import sys


filename = sys.argv[1]
students = []

with open(filename, newline="") as file:
    reader = csv.DictReader(file)
    for row in reader:
        score = (float(row["Math"]) + float(row["Science"]) + float(row["English"])) / 3
        students.append((row["Name"], score))

students.sort(key=lambda student: student[1], reverse=True)

print("Top scoring students:")
print(students[-1])
