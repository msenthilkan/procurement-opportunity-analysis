Two ways to apply the same improvements. Use ONE of them.

OPTION A - script (needs Git for Windows on your laptop)
  1. Open the folder option-A-script
  2. Right-click update-github.ps1 > Run with PowerShell
  3. Log in to GitHub if a browser window asks
  It updates the README, adds the test workflow, deletes dashboard_preview.png,
  and (if GitHub CLI is installed) fills in the About box.

OPTION B - browser only (no installs)
  1. Upload README.md:   repo > Add file > Upload files > drag option-B-browser\README.md > Commit changes
  2. Add the workflow:   repo > Add file > Create new file
                         name:    .github/workflows/scenario-checks.yml
                         content: paste everything from option-B-browser\scenario-checks.yml.txt
                         > Commit changes
  3. Delete the stray image: click dashboard_preview.png > ... (top right) > Delete file > Commit changes
  4. About box: repo main page > gear icon next to "About" > paste description and topics

Description:
  Excel Power Query pipeline for e-procurement spend analysis: buying channels, scope tiers, coverage vs target and country-level actions (synthetic data)
Topics:
  power-query excel procurement spend-analysis sap-ariba data-analytics pareto-analysis
