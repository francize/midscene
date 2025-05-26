import { webExtractNodeTree } from '@midscene/shared/extractor';

// Helper to get the URL of a script in the extension's 'scripts' directory
function getScriptURL(scriptName: string): string {
  return chrome.runtime.getURL(`scripts/${scriptName}`);
}

export const getHtmlElementScript = async (): Promise<string> => {
  const scriptUrl = getScriptURL('htmlElement.js'); // Corrected filename
  try {
    const response = await fetch(scriptUrl);
    if (!response.ok) {
      throw new Error(`Failed to fetch htmlElementScript: ${response.status} ${response.statusText} from ${scriptUrl}`);
    }
    return await response.text();
  } catch (error) {
    console.error('Error fetching htmlElementScript:', error);
    throw error;
  }
};

export const injectWaterFlowAnimation = async () => {
  const scriptUrl = getScriptURL('water-flow.js');
  try {
    const response = await fetch(scriptUrl);
    if (!response.ok) throw new Error(`Failed to fetch waterFlowScript: ${response.status} ${response.statusText} from ${scriptUrl}`);
    const waterFlowScriptText = await response.text();

    // Ensure currentTabId is available and chrome.scripting is defined
    if (typeof chrome !== 'undefined' && chrome.scripting && chrome.tabs) {
      const tabId = await currentTabId();
      await chrome.scripting.executeScript({
        target: { tabId: tabId },
        world: 'MAIN',
        args: [waterFlowScriptText],
        func: (script: string) => {
          const scriptEl = document.createElement('script');
          scriptEl.textContent = script;
          // Append to head, then remove. Or body if head is not guaranteed.
          (document.head || document.body).appendChild(scriptEl)?.remove();
        },
      });
    } else {
      console.warn('chrome.scripting or chrome.tabs API not available. Skipping script injection.');
    }
  } catch (error) {
    console.error('Error injecting waterFlowScript:', error);
  }
};

export const injectStopWaterFlowAnimation = async () => {
  const scriptUrl = getScriptURL('stop-water-flow.js');
   try {
    const response = await fetch(scriptUrl);
    if (!response.ok) throw new Error(`Failed to fetch stopWaterFlowScript: ${response.status} ${response.statusText} from ${scriptUrl}`);
    const stopWaterFlowScriptText = await response.text();
    
    if (typeof chrome !== 'undefined' && chrome.scripting && chrome.tabs) {
      const tabId = await currentTabId();
      await chrome.scripting.executeScript({
        target: { tabId: tabId },
        world: 'MAIN',
        args: [stopWaterFlowScriptText],
        func: (script: string) => {
          const scriptEl = document.createElement('script');
          scriptEl.textContent = script;
          (document.head || document.body).appendChild(scriptEl)?.remove();
        },
      });
    } else {
      console.warn('chrome.scripting or chrome.tabs API not available. Skipping script injection.');
    }
  } catch (error) {
    console.error('Error injecting stopWaterFlowScript:', error);
  }
};

async function currentTabId() {
  // Ensure chrome.tabs is available
  if (typeof chrome !== 'undefined' && chrome.tabs) {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) {
      throw new Error('No active tab found or tab ID is missing.');
    }
    return tab.id;
  }
  throw new Error('chrome.tabs API not available.');
} 