# WhatsApp Reaction Tally System

This toolkit helps you tally points from exported WhatsApp message reactions and easily copy them over to a Master Google Sheet. 

## Initial Setup
1. Drag and drop `Weekly_Tracker_Template.xlsx` into your Google Drive. Open it with Google Sheets.
2. This will be your master tracker. It already contains everyone's names, teams, and formulas.
3. Install the **"Allow Select and Copy"** extension (or similar) on your desktop browser.

## Daily Workflow
1. Open WhatsApp Web on your computer.
2. Click the reactions popup on a message, use the extension to highlight the entire messy popup of names/status messages, and Copy it (`Ctrl+C`).
3. Paste that raw text into a blank `.txt` file (e.g. `task1.txt`) and save it into the `tocount` folder. 
4. Double-click or run `python countvotes.py`.
5. The script scans the text, matches people to your master list, and outputs tally files inside the `output` folder. (The original `.txt` files are moved to `archive` so they aren't double-counted).
6. Open your main Google Sheet and go to today's tab (e.g. `Day 1`).
7. Open the generated `output/tally_...csv`. Highlight **only the numbers** in the "Points" column from top to bottom. Copy them (`Ctrl+C`).
8. Go to your Google Sheet, click the top empty cell in your task column, and Paste (`Ctrl+V`). The numbers will perfectly align with everyone's names!

## Dealing With New Members
If a new person reacts to a message:
1. Because the script reads a messy raw text dump instead of a neat spreadsheet, it **cannot safely auto-detect new members** without accidentally adding random status messages or words to your team sheet.
2. You must **manually type their Name and Team** at the bottom of your `master_list.csv` (and Google Sheet tabs) *before* you run `countvotes.py`. Once their name is in the master list, the script will find them perfectly in the `.txt` exports!
