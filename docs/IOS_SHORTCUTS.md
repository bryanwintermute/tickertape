# Apple iOS Shortcuts & Share Sheet Support

You can easily send content from your iPhone or iPad directly to Tickertape using two methods:

## Method 1: Web Share Target (PWA)
If you've added Tickertape to your Home Screen (as a PWA), it automatically registers itself as a Share Target.
1. Highlight text or open a URL on your phone.
2. Tap the standard iOS **Share** button.
3. Tap **Tickertape** in the app list.
4. The Tickertape app will open with the content pre-filled in the Markdown tab, ready for you to adjust and tap "Print".

## Method 2: Apple Shortcuts (Direct Print)
If you want to print content instantly *without* opening the UI first, you can create a custom iOS Shortcut.

1. Open the **Shortcuts** app on iOS.
2. Tap **+** to create a new shortcut.
3. In the right-hand settings panel, enable **Show in Share Sheet**. (Set it to accept Text, URLs, and Rich Text).
4. Add a **Dictionary** action:
   - Key: `type` (Text), Value: `echo`
   - Key: `text` (Text), Value: `Shortcut Input` (Select the input from the share sheet)
5. Add a **Get contents of URL** action:
   - URL: `http://10.20.0.139:8000/api/print` (replace with your Wireguard/LAN IP if necessary)
   - Method: `POST`
   - Headers: `Content-Type` : `application/json`
   - Request Body: `File` -> Select the Dictionary variable from step 4.
6. Save the shortcut as "Print to Tickertape".

Now, whenever you share text to this Shortcut, it will fire an API request in the background and instantly print the receipt!

## See also

- [`ANDROID_SHARE.md`](./ANDROID_SHARE.md) — the Android equivalents, including why the share sheet works from Chrome but not Firefox.
