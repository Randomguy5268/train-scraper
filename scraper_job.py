
name: Shinkansen Scraper

on:
  schedule:
    - cron: '*/5 * * * *' # Runs the scraper every 5 minutes
  workflow_dispatch: # Allows you to manually click a button to run it

# CRITICAL: These permissions are required for Workload Identity Federation to generate tokens
permissions:
  contents: 'read'
  id-token: 'write'

jobs:
  scrape-and-update:
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements_scraper.txt
          playwright install --with-deps chromium

      - name: Authenticate to Google Cloud keyless
        id: auth
        uses: google-github-actions/auth@v2
        with:
          # Paste the string from your Cloud Shell output below:
          workload_identity_provider: 'projects/831888210715/locations/global/workloadIdentityPools/github-pool/providers/github-provider'
          service_account: 'shinkansen-scraper@project-ef09c9bb-3689-4f27-8cf.iam.gserviceaccount.com'

      - name: Run Scraper
        run: python scraper_job.py
