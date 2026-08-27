import csv #to read csv files
import sys #to read command line arguments


filename = sys.argv[1] #get csv file name from 1st command line argument
students = [] #initialize empty list to store student names and scores

with open(filename, newline="") as file: #newline="" to avoid extra blank lines in output, accepts all formats of newlines
    reader = csv.DictReader(file) 
    for row in reader:
        score = (float(row["Math"]) + float(row["Science"]) + float(row["English"])) / 3 #calculate average score for each student with correct data type conversion
        students.append((row["Name"], score)) 

students.sort(key=lambda student: student[1], reverse=True) # use student[1] average score to sort, lambda function is used to extract the score from each tuple

print("Top scoring students:")
print(students[0][0]) 
