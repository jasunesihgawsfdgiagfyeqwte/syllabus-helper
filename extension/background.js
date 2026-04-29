chrome.contextMenus.create({
  id: "upload-syllabus",
  title: "Upload to Syllabus Helper",
  contexts: ["link"],
  targetUrlPatterns: ["*://*/*.pdf", "*://*/*.docx"]
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "upload-syllabus") {
    chrome.tabs.create({ url: "https://syllabushelper.net/#upload" });
  }
});
