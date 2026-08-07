# teacher-ai-lab-2026
Dr. Gift's upstream repository of necessary files

To link your repo with mine, do this ONE TIME:
1. Open Terminal/Command Prompt
2. Navigate to your GitHub folder
3. Type the following prompt:
git remote add upstream https://github.com/DanielGift/teacher-ai-lab-2026.git
4. Type the following:
git pull upstream main --allow-unrelated-histories
5. Type:
git remote add origin YOUR_REPO_LINK_HERE
(You can find your repo link on GitHub, if you click on the upper right green button that says "Code" and copy the URL that shows up)
6. Type:
git push origin main

To get any updates I add, do this EACH TIME:
1. Open GitHub Desktop and make sure you are on your main or master branch.
2. In the top menu, click Branch -> Merge into current branch.
3. A menu will pop up. Look at the list of branches.Select upstream/main (or upstream/master).
4. Click the large Merge upstream/main into main button at the bottom.
5. If you want to change the location of the new file, that is best dine in Finder/File Explorer. You can reach this from GitHub Desktop by clicking **Repository -> Show in Finder (Mac) or Show in Explorer (Windows)**
6. Click the blue Push origin button at the top of your screen to save those new files to your personal GitHub website.
7. Note: If there is a conflict because you modified a file that I changed, you will be guided through a merge. You should generally just take my new code, but there may be times where you added lines that you want to keep too.



Alternative update instructions for those who prefer the command line
1. Open Terminal/Command Prompt
2. Navigate to your GitHub folder
3. Type the following prompt:
   git pull upstream main 
4. Move any new files to where they need to go with the command:
   git mv FILENAME FOLDER_TO_MOVE_TO
5. Push the updates to your online repository:
   git push origin main

