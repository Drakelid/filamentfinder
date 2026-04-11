# FilamentFinder Chrome Extension

This folder contains a no-build Manifest V3 Chrome extension for capturing selectors on live storefronts and saving scrape templates to FilamentFinder.

## Generate icons

Run the icon generator once from the repo root or from this folder:

```bash
python chrome-ext/generate-icons.py
```

If you are already inside `chrome-ext/`, use:

```bash
python generate-icons.py
```

This creates:

- `icons/icon16.png`
- `icons/icon48.png`
- `icons/icon128.png`

## Load the extension in Chrome

1. Open `chrome://extensions/`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select the `chrome-ext/` folder

## Configure the extension

1. Open the extension popup
2. Go to the **Settings** tab
3. Enter your FilamentFinder base URL, for example `https://your-filamentfinder.domain`
4. Enter the API key if your backend requires `X-API-Key`
5. Click **Save Settings**
6. Use **Test Connection** to confirm the API is reachable

## Use the picker

1. Open a product or listing page on the target store
2. Open the extension popup and switch to **Template Builder**
3. Fill in the template name, parser label, and optional description
4. Click **Pick** next to the selector field you want to capture
5. The popup closes so you can click the page element directly
6. Click the target element on the site, then reopen the popup to review the captured selector
7. Repeat for any remaining fields, expand **Crawl Rules** if needed, and click **Save Template**

Press `Escape` while picking to cancel.
