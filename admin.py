"""
Awareness Challenge — Admin Dashboard Server
Run:  python admin.py
Open: http://localhost:8080
"""
import csv
import json
import os
import re
import subprocess
from collections import defaultdict
from datetime import datetime

from flask import Flask, jsonify, request, send_file

# ── Configuration ──────────────────────────────────────────────
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '123')   # Default to 123 locally if not set
PORT = 8080
MASTER_LIST = 'master_list.csv'
LEADERBOARD_JS = 'leaderboard_data.js'
TO_COUNT_DIR = 'tocount'
ARCHIVE_DIR = 'archive'

TEAM_META = {
    'The Kangaroos':    {'emoji': '🦘', 'order': 0},
    'The Koalas':       {'emoji': '🐨', 'order': 1},
    'The Flying Foxes': {'emoji': '🦇', 'order': 2},
    'The Dingoes':      {'emoji': '🐺', 'order': 3},
    'The Sharks':       {'emoji': '🦈', 'order': 4},
    'The Crocs':        {'emoji': '🐊', 'order': 5},
}

app = Flask(__name__)


# ── Helpers ────────────────────────────────────────────────────

def check_password():
    """Return an error response if password is missing/wrong, else None."""
    pw = request.headers.get('X-Admin-Password', '')
    if pw != ADMIN_PASSWORD:
        return jsonify({'error': 'Wrong password'}), 403
    return None


def read_master_list():
    """Read master_list.csv and return list of dicts."""
    users = []
    with open(MASTER_LIST, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            users.append(row)
    return users


def write_master_list(users):
    """Write users back to master_list.csv."""
    with open(MASTER_LIST, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['Team', 'Name', 'Today Points', 'Total Points'])
        writer.writeheader()
        for u in users:
            writer.writerow(u)


def regenerate_leaderboard(users):
    """Regenerate leaderboard_data.js from the given user list."""
    teams_data = defaultdict(lambda: {'members': [], 'totalPoints': 0})
    for u in users:
        team = u['Team']
        pts = int(u.get('Total Points', 0) or 0)
        teams_data[team]['members'].append({'name': u['Name'], 'points': pts})
        teams_data[team]['totalPoints'] += pts

    teams_list = []
    for team_name in sorted(TEAM_META.keys(), key=lambda t: TEAM_META[t]['order']):
        td = teams_data.get(team_name, {'members': [], 'totalPoints': 0})
        td['members'].sort(key=lambda m: (-m['points'], m['name']))
        teams_list.append({
            'name': team_name,
            'emoji': TEAM_META[team_name]['emoji'],
            'members': td['members']
        })

    data = {
        'lastUpdated': datetime.now().strftime('%d %b %Y, %I:%M %p'),
        'teams': teams_list
    }

    with open(LEADERBOARD_JS, 'w', encoding='utf-8') as f:
        f.write('const LEADERBOARD_DATA = ')
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write(';\n')

    return data


def split_into_sections(raw_text):
    """Split a WhatsApp poll text dump into individual poll sections."""
    # Normalize line endings
    text = raw_text.replace('\r\n', '\n').replace('\r', '\n')
    # Split on blank line(s) followed by a poll header (a name + "Click to remove")
    # Each section starts with someone's name on a line by itself
    sections = re.split(r'\n\n+(?=\S+\n(?:Click to remove)?)', text.strip())
    return [s for s in sections if s.strip()]


def extract_names_from_section(section, master_names):
    """
    Extract matched master-list names from a poll section.
    Uses FIRST-WORD matching to avoid substring false positives.
    
    E.g. "Manju syd" matches master name "Manju" but NOT "Anju".
    """
    matched = set()
    lines = section.strip().split('\n')

    # Build a lookup: lowercase first name → original name
    name_lookup = {}
    for name in master_names:
        name_lookup[name.strip().lower()] = name

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Skip UI artifacts
        if line.lower() in ('click to remove', 'you'):
            continue
        # Skip lines that are just emoji (single character or known reaction emoji)
        if len(line) <= 4 and not line[0].isalpha():
            continue
        # Also skip standalone single-letter lines (like "V" or "M" which are UI artifacts)
        if len(line) == 1:
            continue

        # Extract first word of the line as the candidate name
        first_word = line.split()[0].strip().lower()

        # Check if first word matches a master list name exactly
        if first_word in name_lookup:
            matched.add(name_lookup[first_word])

    return matched


def tally_file(raw_text, users):
    """
    Tally a score file: split into sections, count per-section,
    return dict of {name: points_earned}.
    """
    master_names = [u['Name'] for u in users]
    sections = split_into_sections(raw_text)
    points = defaultdict(int)
    section_details = []

    for i, section in enumerate(sections):
        matched = extract_names_from_section(section, master_names)
        for name in matched:
            points[name] += 1
        section_details.append({
            'section': i + 1,
            'matched': sorted(matched),
            'count': len(matched)
        })

    return dict(points), section_details


# ── Routes ─────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_file('admin.html')


@app.route('/api/status')
def status():
    users = read_master_list()
    teams = defaultdict(lambda: {'members': [], 'total': 0})
    for u in users:
        pts = int(u.get('Total Points', 0) or 0)
        teams[u['Team']]['members'].append({'name': u['Name'], 'points': pts})
        teams[u['Team']]['total'] += pts

    result = []
    for team_name in sorted(TEAM_META.keys(), key=lambda t: TEAM_META[t]['order']):
        td = teams.get(team_name, {'members': [], 'total': 0})
        result.append({
            'name': team_name,
            'emoji': TEAM_META[team_name]['emoji'],
            'total': td['total'],
            'members': sorted(td['members'], key=lambda m: (-m['points'], m['name']))
        })

    return jsonify({'teams': result})


@app.route('/api/upload', methods=['POST'])
def upload():
    err = check_password()
    if err:
        return err

    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Empty filename'}), 400

    raw_text = file.read().decode('utf-8', errors='ignore')
    users = read_master_list()

    # Tally
    new_points, section_details = tally_file(raw_text, users)

    if not any(v > 0 for v in new_points.values()):
        return jsonify({'error': 'No names matched. Check the file format.'}), 400

    # Add points to existing totals
    changes = []
    for u in users:
        added = new_points.get(u['Name'], 0)
        if added > 0:
            old_total = int(u.get('Total Points', 0) or 0)
            new_total = old_total + added
            old_today = int(u.get('Today Points', 0) or 0)
            u['Today Points'] = str(old_today + added)
            u['Total Points'] = str(new_total)
            changes.append({
                'name': u['Name'],
                'team': u['Team'],
                'added': added,
                'oldTotal': old_total,
                'newTotal': new_total
            })

    write_master_list(users)
    regenerate_leaderboard(users)

    # Save file to archive
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    archive_path = os.path.join(ARCHIVE_DIR, file.filename)
    file.seek(0)
    with open(archive_path, 'wb') as f:
        f.write(file.read())

    total_added = sum(new_points.values())
    return jsonify({
        'success': True,
        'filename': file.filename,
        'totalPointsAdded': total_added,
        'sectionsFound': len(section_details),
        'changes': changes,
        'sections': section_details
    })


@app.route('/api/bonus', methods=['POST'])
def bonus():
    err = check_password()
    if err:
        return err

    data = request.get_json()
    team_name = data.get('team', '')
    if team_name not in TEAM_META:
        return jsonify({'error': f'Unknown team: {team_name}'}), 400

    users = read_master_list()
    changes = []
    for u in users:
        if u['Team'] == team_name:
            old_total = int(u.get('Total Points', 0) or 0)
            old_today = int(u.get('Today Points', 0) or 0)
            u['Total Points'] = str(old_total + 1)
            u['Today Points'] = str(old_today + 1)
            changes.append({'name': u['Name'], 'newTotal': old_total + 1})

    write_master_list(users)
    regenerate_leaderboard(users)

    return jsonify({
        'success': True,
        'team': team_name,
        'membersUpdated': len(changes),
        'changes': changes
    })


@app.route('/api/individual', methods=['POST'])
def individual():
    err = check_password()
    if err:
        return err

    data = request.get_json()
    person_name = data.get('name', '').strip()
    if not person_name:
        return jsonify({'error': 'No name provided'}), 400

    users = read_master_list()
    found = False
    new_total = 0
    team = ''
    for u in users:
        if u['Name'] == person_name:
            old_total = int(u.get('Total Points', 0) or 0)
            old_today = int(u.get('Today Points', 0) or 0)
            u['Total Points'] = str(old_total + 1)
            u['Today Points'] = str(old_today + 1)
            new_total = old_total + 1
            team = u['Team']
            found = True
            break

    if not found:
        return jsonify({'error': f'Person not found: {person_name}'}), 404

    write_master_list(users)
    regenerate_leaderboard(users)

    return jsonify({
        'success': True,
        'name': person_name,
        'team': team,
        'newTotal': new_total
    })


@app.route('/api/add_member', methods=['POST'])
def add_member():
    err = check_password()
    if err:
        return err

    data = request.get_json()
    person_name = data.get('name', '').strip()
    team_name = data.get('team', '').strip()

    if not person_name:
        return jsonify({'error': 'Name is required'}), 400
    if team_name not in TEAM_META:
        return jsonify({'error': f'Unknown team: {team_name}'}), 400

    users = read_master_list()

    # Check for duplicate
    for u in users:
        if u['Name'].lower() == person_name.lower():
            return jsonify({'error': f'{person_name} already exists in {u["Team"]}'}), 400

    users.append({
        'Team': team_name,
        'Name': person_name,
        'Today Points': '0',
        'Total Points': '0'
    })

    write_master_list(users)
    regenerate_leaderboard(users)

    return jsonify({
        'success': True,
        'name': person_name,
        'team': team_name,
        'message': f'{person_name} added to {team_name}'
    })


@app.route('/api/reset', methods=['POST'])
def reset():
    err = check_password()
    if err:
        return err

    users = read_master_list()
    for u in users:
        u['Today Points'] = '0'
        u['Total Points'] = '0'

    write_master_list(users)
    regenerate_leaderboard(users)

    return jsonify({'success': True, 'message': 'All points reset to zero.'})


@app.route('/api/publish', methods=['POST'])
def publish():
    err = check_password()
    if err:
        return err

    try:
        # Cloud Git Auth
        token = os.environ.get('GITHUB_TOKEN')
        push_cmd = ['git', 'push']
        
        if token:
            repo_slug = os.environ.get('RENDER_GIT_REPO_SLUG')
            if repo_slug:
                repo_url = f"https://oauth2:{token}@github.com/{repo_slug}.git"
                push_cmd = ['git', 'push', repo_url, 'HEAD:main']
            else:
                try:
                    repo_url = subprocess.check_output(['git', 'config', '--get', 'remote.origin.url']).decode().strip()
                    if 'github.com' in repo_url and '@' not in repo_url:
                        repo_url = repo_url.replace('https://', f'https://oauth2:{token}@')
                    push_cmd = ['git', 'push', repo_url, 'HEAD:main']
                except Exception:
                    pass
                    
            # Set minimum identity so cloud servers don't complain
            subprocess.run(['git', 'config', 'user.name', 'Awareness Admin Bot'])
            subprocess.run(['git', 'config', 'user.email', 'admin-bot@awareness.local'])

        # Force-regenerate leaderboard_data.js from current master_list
        users = read_master_list()
        regenerate_leaderboard(users)

        # Stage everything (admin.py, admin.html, master_list.csv, and leaderboard)
        subprocess.run(['git', 'add', '-A'], capture_output=True, text=True)

        # Try to commit — may fail if nothing changed, that's OK
        commit_result = subprocess.run(
            ['git', 'commit', '-m', f'Update leaderboard — {datetime.now().strftime("%d %b %Y %I:%M %p")}'],
            capture_output=True, text=True
        )

        # Push using the constructed command
        push_result = subprocess.run(push_cmd, capture_output=True, text=True)

        if push_result.returncode != 0:
            # Mask the token in the error message if it exists
            err_msg = push_result.stderr or push_result.stdout
            if token:
                err_msg = err_msg.replace(token, '***TOKEN***')
            return jsonify({'error': f'Push failed: {err_msg}'}), 500

        if commit_result.returncode != 0 and 'nothing to commit' in (commit_result.stdout + commit_result.stderr):
            return jsonify({'success': True, 'message': 'Already up to date — no new changes to publish.'})

        return jsonify({'success': True, 'message': 'Pushed to GitHub! Live site will update shortly.'})
    except Exception as e:
        return jsonify({'error': f'Error: {str(e)}'}), 500


if __name__ == '__main__':
    print(f"\n🏆 Awareness Challenge Admin Dashboard")
    print(f"   Open: http://localhost:{PORT}")
    print(f"   Password: {ADMIN_PASSWORD}\n")
    app.run(host='0.0.0.0', port=PORT, debug=True)
