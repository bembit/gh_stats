import requests
from collections import defaultdict
from colorama import Fore, Style, init

from datetime import datetime

from dotenv import dotenv_values

# HOWTO:
# 1. create a .env file in the same folder as the script
# 2. add USERNAME and TOKEN.
# 3. run the script
# 4. have a coffee

# notes:
# 1. add check for invited / no ownership repos --> check the username, swap to username / reponame.
# 2. check for libraries and shit and ignore them.
# 3. index folder names ? skip repeating stuff ?
# 4. will finish I promise, like the rest of my 89 repos.
# 5. let me go back to CSS pls.

# set up GH API classic token
USERNAME = dotenv_values(".env")["USERNAME"]
TOKEN = dotenv_values(".env")["TOKEN"]

# colorama
init(autoreset=True)

# colors for specific extensions / allowed to scan extensions
# SKIPS everything that is not in this list ( jsx really ? )
extension_colors = {
    "css": Fore.CYAN,
    "sass": Fore.CYAN,
    "scss": Fore.CYAN,
    "html": Fore.RED,
    "htm": Fore.RED,
    "ejs": Fore.RED,
    "astro": Fore.RED,
    "js": Fore.YELLOW,
    "jsx": Fore.YELLOW,
    "ts": Fore.YELLOW,
    "tsx": Fore.YELLOW,
    "vue": Fore.GREEN,
    "svelte": Fore.GREEN,
    "py": Fore.BLUE,
    "ps1": Fore.BLUE,
    "sh": Fore.BLUE,
}

# work from colors keys
allowed_extensions = set(extension_colors.keys())

def get_repositories(limit=None, year=None):
    url = "https://api.github.com/user/repos"
    headers = {"Authorization": f"token {TOKEN}"}
    repos = []
    page = 1

    while True:
        response = requests.get(
            url,
            headers=headers,
            params={
                "per_page": 100,
                "page": page,
                "visibility": "all",
                "affiliation": "owner,collaborator,organization_member",
            },
        )
        if response.status_code != 200:
            print(f"{Fore.RED}[ERROR] Fetching repositories: {response.json()}{Style.RESET_ALL}")
            break
        data = response.json()
        if not data:
            break

        for repo in data:
            created_at = datetime.strptime(repo['created_at'], "%Y-%m-%dT%H:%M:%SZ")
            if year is None or created_at.year == year:
                repos.append(repo)

        page += 1
        if limit and len(repos) >= limit:
            repos = repos[:limit]
            break

    return repos

def get_file_lines(repo_name, owner, path=""):
    url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{path}"
    headers = {"Authorization": f"token {TOKEN}"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"{Fore.RED}[ERROR] Unable to fetch contents of {owner}/{repo_name}/{path}: {response.status_code}{Style.RESET_ALL}")
        return 0, defaultdict(int)

    # use try/except to show you know what you are doing
    try:
        files = response.json()
        if not isinstance(files, list):
            print(f"{Fore.RED}[ERROR] Unexpected format in {owner}/{repo_name}/{path}: {files}{Style.RESET_ALL}")
            return 0, defaultdict(int)
    except ValueError:
        print(f"{Fore.RED}[ERROR] JSON decode error in {owner}/{repo_name}/{path}: {response.text}{Style.RESET_ALL}")
        return 0, defaultdict(int)

    file_counts = defaultdict(int)
    total_lines = 0

    for file in files:
        if file.get('type') == 'file':
            extension = file['name'].split('.')[-1] if '.' in file['name'] else None

            if extension not in allowed_extensions:
                print(f"{Fore.LIGHTBLACK_EX}[SKIP] Ignoring file: {owner}/{repo_name}/{file['path']} (Extension: {extension}){Style.RESET_ALL}")
                continue

            # print current file
            print(f"{Fore.GREEN}[FILE] Processing file: {owner}/{repo_name}/{file['path']}{Style.RESET_ALL}")
            raw_file_response = requests.get(file['download_url'])
            if raw_file_response.status_code == 200:
                raw_file = raw_file_response.text
                
                # calculate metrics
                lines = len(raw_file.splitlines())
                words = sum(len(line.split()) for line in raw_file.splitlines())
                characters = len(raw_file)

                # update totals
                total_lines += lines
                file_counts[extension] += lines

                # metrics are good
                print(
                    # validate if javascript or css/scss files are larger than 1500 lines. if so, print a warning ( later i will add a flag to ignore these most likely unnecessary files )
                    f"{extension_colors[extension]}    [METRICS] Lines: {lines}, Words: {words}, Characters: {characters}{Style.RESET_ALL}" if lines < 1500 else f"{extension_colors[extension]}    [METRICS] Lines: {lines}, Words: {words}, Characters: {characters}{Style.RESET_ALL}\n{Fore.YELLOW}[WARNING] This file is larger than 1500 lines and may be too large to be processed.{Style.RESET_ALL}"
                    # f"{extension_colors[extension]}    [METRICS] Lines: {lines}, Words: {words}, Characters: {characters}{Style.RESET_ALL}"
                )
            else:
                print(f"{Fore.RED}[ERROR] Unable to fetch file: {owner}/{repo_name}/{file['path']}{Style.RESET_ALL}")

        elif file.get('type') == 'dir':
            print(f"{Fore.BLUE}[DIR] Traversing directory: {owner}/{repo_name}/{file['path']}{Style.RESET_ALL}")
            sub_total, sub_counts = get_file_lines(repo_name, owner, file['path'])
            total_lines += sub_total
            for ext, count in sub_counts.items():
                file_counts[ext] += count

    return total_lines, file_counts

def write_summary_to_file(repo_name, total_lines, file_counts, output_file="repo_stats.txt"):
    with open(output_file, "a") as file:
        file.write(f"Repository: {repo_name}\n")
        file.write(f"Total Lines: {total_lines}\n")
        file.write("File Type Statistics:\n")
        for ext, count in file_counts.items():
            file.write(f"  {ext}: {count} lines\n")
        file.write("\n")

def main():
    # prompt for year or enter scan all, no input validation in case you want to check you repos from 4090 or from the civil war
    print(f"{Fore.CYAN}[PROMPT] Do you want to filter repositories by creation year? (Enter a year or press Enter to scan all){Style.RESET_ALL}")
    year_input = input("Year: ").strip()
    year = int(year_input) if year_input.isdigit() else None

    print(f"{Fore.CYAN}[INFO] Fetching repositories...{Style.RESET_ALL}")
    repositories = get_repositories(year=year)

    if not repositories:
        print(f"{Fore.YELLOW}[INFO] No repositories found for the specified criteria.{Style.RESET_ALL}")
        return

    # process each repository
    overall_file_counts = defaultdict(int)
    for repo in repositories:
        repo_name = repo['name']
        print(f"\n{Fore.MAGENTA}[REPO] Processing repository: {repo_name}{Style.RESET_ALL}")
        total_lines, file_counts = get_file_lines(repo_name, owner=USERNAME)
        print(f"{Fore.CYAN}[REPO] Total lines in {repo_name}: {total_lines}{Style.RESET_ALL}")
        for ext, count in file_counts.items():
            overall_file_counts[ext] += count
   
        # optionally write the summary to a file ( i needed )
        write_summary_to_file(repo_name, total_lines, file_counts)
        print(f"{Fore.GREEN}[INFO] Summary written to file for repository: {repo_name}{Style.RESET_ALL}")
   
    # display overall stats
    print(f"\n{Fore.MAGENTA}[SUMMARY] Overall File Type Statistics:{Style.RESET_ALL}")
    for ext, count in overall_file_counts.items():
        print(f"{Fore.MAGENTA}{ext}: {count} lines{Style.RESET_ALL}")

    print(f"\n{Fore.MAGENTA}[SUMMARY] Overall File Type Statistics - Repo count: {len(repositories)}{Style.RESET_ALL}")
    for ext, count in overall_file_counts.items():
        # unknown extensions
        color = extension_colors.get(ext, Fore.WHITE)
        print(f"{color}{ext}: {count} lines{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
