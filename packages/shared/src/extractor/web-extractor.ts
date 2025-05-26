import {
  CONTAINER_MINI_HEIGHT,
  CONTAINER_MINI_WIDTH,
  NodeType,
} from '../constants/index';
import type { WebElementInfo } from '../types';
import type { Point } from '../types';
import {
  isButtonElement,
  isContainerElement,
  isFormElement,
  isImgElement,
  isTextElement,
} from './dom-util';
import { descriptionOfTree } from './tree';
import {
  elementRect,
  getNodeAttributes,
  getPseudoElementContent,
  getRect,
  getTopDocument,
  logger,
  midsceneGenerateHash,
  setDataForNode,
  setDebugMode,
} from './util';

let indexId = 0;

function tagNameOfNode(node: globalThis.Node): string {
  let tagName = '';
  if (node instanceof HTMLElement) {
    tagName = node.tagName.toLowerCase();
  }

  const parentElement = node.parentElement;
  if (parentElement && parentElement instanceof HTMLElement) {
    tagName = parentElement.tagName.toLowerCase();
  }

  return tagName ? `<${tagName}>` : '';
}

export function collectElementInfo(
  node: Node,
  currentWindow: typeof window,
  currentDocument: typeof document,
  baseZoom = 1,
  basePoint: Point = { left: 0, top: 0 },
  visibleOnly = true,
): WebElementInfo | null | any {
  const rect = elementRect(
    node,
    currentWindow,
    currentDocument,
    baseZoom,
    visibleOnly,
  );

  if (!rect) {
    return null;
  }

  if (
    node !== currentDocument.body &&
    visibleOnly &&
    (rect.width < CONTAINER_MINI_WIDTH || rect.height < CONTAINER_MINI_HEIGHT)
  ) {
    return null;
  }

  if (basePoint.left !== 0 || basePoint.top !== 0) {
    rect.left += basePoint.left;
    rect.top += basePoint.top;
  }
  // Skip elements that cover the entire viewport, as they are likely background containers
  // rather than meaningful interactive elements. This check should not apply to document.body itself.
  if (
    node !== currentDocument.body &&
    rect.height >= currentWindow.innerHeight &&
    rect.width >= currentWindow.innerWidth
  ) {
    return null;
  }

  if (isFormElement(node)) {
    const attributes = getNodeAttributes(node, currentWindow);
    let valueContent =
      attributes.value || attributes.placeholder || node.textContent || '';
    const nodeHashId = midsceneGenerateHash(node, valueContent, rect);
    const selector = setDataForNode(node, nodeHashId, false, currentWindow);
    const tagName = (node as HTMLElement).tagName.toLowerCase();
    if ((node as HTMLElement).tagName.toLowerCase() === 'select') {
      // Get the selected option using the selectedIndex property
      const selectedOption = (node as HTMLSelectElement).options[
        (node as HTMLSelectElement).selectedIndex
      ];

      // Retrieve the text content of the selected option
      valueContent = selectedOption.textContent || '';
    }

    if (
      ((node as HTMLElement).tagName.toLowerCase() === 'input' ||
        (node as HTMLElement).tagName.toLowerCase() === 'textarea') &&
      (node as HTMLInputElement).value
    ) {
      valueContent = (node as HTMLInputElement).value;
    }

    const elementInfo: WebElementInfo = {
      id: nodeHashId,
      nodeHashId,
      locator: selector,
      nodeType: NodeType.FORM_ITEM,
      indexId: indexId++,
      attributes: {
        ...attributes,
        htmlTagName: `<${tagName}>`,
        nodeType: NodeType.FORM_ITEM,
      },
      content: valueContent.trim(),
      rect,
      center: [
        Math.round(rect.left + rect.width / 2),
        Math.round(rect.top + rect.height / 2),
      ],
      zoom: rect.zoom,
    };
    return elementInfo;
  }

  if (isButtonElement(node)) {
    const attributes = getNodeAttributes(node, currentWindow);
    const pseudo = getPseudoElementContent(node, currentWindow);
    const content = node.innerText || pseudo.before || pseudo.after || '';
    const nodeHashId = midsceneGenerateHash(node, content, rect);
    const selector = setDataForNode(node, nodeHashId, false, currentWindow);
    const elementInfo: WebElementInfo = {
      id: nodeHashId,
      indexId: indexId++,
      nodeHashId,
      nodeType: NodeType.BUTTON,
      locator: selector,
      attributes: {
        ...attributes,
        htmlTagName: tagNameOfNode(node),
        nodeType: NodeType.BUTTON,
      },
      content,
      rect,
      center: [
        Math.round(rect.left + rect.width / 2),
        Math.round(rect.top + rect.height / 2),
      ],
      zoom: rect.zoom,
    };
    return elementInfo;
  }

  if (isImgElement(node)) {
    const attributes = getNodeAttributes(node, currentWindow);
    const nodeHashId = midsceneGenerateHash(node, '', rect);
    const selector = setDataForNode(node, nodeHashId, false, currentWindow);
    const elementInfo: WebElementInfo = {
      id: nodeHashId,
      indexId: indexId++,
      nodeHashId,
      locator: selector,
      attributes: {
        ...attributes,
        ...(node.nodeName.toLowerCase() === 'svg'
          ? {
              svgContent: 'true',
            }
          : {}),
        nodeType: NodeType.IMG,
        htmlTagName: tagNameOfNode(node),
      },
      nodeType: NodeType.IMG,
      content: '',
      rect,
      center: [
        Math.round(rect.left + rect.width / 2),
        Math.round(rect.top + rect.height / 2),
      ],
      zoom: rect.zoom,
    };
    return elementInfo;
  }

  if (isTextElement(node)) {
    const text = node.textContent?.trim().replace(/\n+/g, ' ');
    if (!text) {
      return null;
    }
    const attributes = getNodeAttributes(node, currentWindow);
    const attributeKeys = Object.keys(attributes);
    if (!text.trim() && attributeKeys.length === 0) {
      return null;
    }
    const nodeHashId = midsceneGenerateHash(node, text, rect);
    const selector = setDataForNode(node, nodeHashId, true, currentWindow);
    const elementInfo: WebElementInfo = {
      id: nodeHashId,
      indexId: indexId++,
      nodeHashId,
      nodeType: NodeType.TEXT,
      locator: selector,
      attributes: {
        ...attributes,
        nodeType: NodeType.TEXT,
        htmlTagName: tagNameOfNode(node),
      },
      center: [
        Math.round(rect.left + rect.width / 2),
        Math.round(rect.top + rect.height / 2),
      ],
      content: text,
      rect,
      zoom: rect.zoom,
    };
    return elementInfo;
  }

  // else, consider as a container
  if (isContainerElement(node)) {
    const attributes = getNodeAttributes(node, currentWindow);
    const nodeHashId = midsceneGenerateHash(node, '', rect);
    const selector = setDataForNode(node, nodeHashId, false, currentWindow);
    const elementInfo: WebElementInfo = {
      id: nodeHashId,
      nodeHashId,
      indexId: indexId++,
      nodeType: NodeType.CONTAINER,
      locator: selector,
      attributes: {
        ...attributes,
        nodeType: NodeType.CONTAINER,
        htmlTagName: tagNameOfNode(node),
      },
      content: '',
      rect,
      center: [
        Math.round(rect.left + rect.width / 2),
        Math.round(rect.top + rect.height / 2),
      ],
      zoom: rect.zoom,
    };
    return elementInfo;
  }
  return null;
}

interface WebElementNode {
  node: WebElementInfo | null;
  children: WebElementNode[];
}

// @deprecated
export function extractTextWithPosition(
  initNode: globalThis.Node,
  debugMode = false,
): WebElementInfo[] {
  const elementNode = extractTreeNode(initNode, debugMode);
  const elementInfoArray: WebElementInfo[] = [];

  // Guard against elementNode being null
  if (!elementNode) {
    return elementInfoArray; // Return empty array if no tree
  }

  function dfsRecursive(node: WebElementNode) {
    if (node.node) {
      elementInfoArray.push(node.node);
    }
    for (let i = 0; i < node.children.length; i++) {
      dfsRecursive(node.children[i]);
    }
  }
  dfsRecursive(elementNode); // Start DFS from the root of the extracted tree
  return elementInfoArray;
}

export function extractTreeNodeAsString(
  initNode: globalThis.Node,
  debugMode = true,
): string {
  const elementNode = extractTreeNode(initNode, debugMode);
  return elementNode ? descriptionOfTree(elementNode) : '';
}

function dfs(
  node: globalThis.Node,
  currentWindow: typeof globalThis.window,
  currentDocument: typeof globalThis.document,
  baseZoom = 1,
  basePoint: Point = { left: 0, top: 0 },
): WebElementNode | null {
  if (!node) {
    return null;
  }

  if (node.nodeType && node.nodeType === 10) {
    // Doctype node
    return null;
  }

  const elementInfo = collectElementInfo(
    node,
    currentWindow,
    currentDocument,
    baseZoom,
    basePoint,
  );

  // Special handling for IFRAME content
  if (node instanceof currentWindow.HTMLIFrameElement && elementInfo) {
    const iframeNode = node as HTMLIFrameElement;
    const childrenOfIframe: WebElementNode[] = [];
    if (iframeNode.contentDocument && iframeNode.contentWindow) {
      const iframeContentRoot = dfs(
        iframeNode.contentDocument.body,
        iframeNode.contentWindow as any,
        iframeNode.contentDocument,
        elementInfo.zoom, // Use the zoom calculated for the iframe element itself
        // Pass the iframe's own absolute coordinates as the base for its content
        { left: elementInfo.rect.left, top: elementInfo.rect.top },
      );
      if (iframeContentRoot) {
        // The content of the iframe is represented by iframeContentRoot.
        // If iframeContentRoot.node is null (e.g. iframe body was skipped but had children),
        // add its children directly. Otherwise, add the whole iframeContentRoot (body node + its children).
        if (iframeContentRoot.node === null && iframeContentRoot.children.length > 0) {
          childrenOfIframe.push(...iframeContentRoot.children);
        } else {
          childrenOfIframe.push(iframeContentRoot); // This will be {node: iframeBodyInfo, children: iframeBodyChildren}
        }
      }
    }
    return { node: elementInfo, children: childrenOfIframe };
  }

  // If it's a leaf-like node, return early (no children processing needed)
  if (
    elementInfo &&
    (elementInfo.nodeType === NodeType.BUTTON ||
      elementInfo.nodeType === NodeType.IMG ||
      elementInfo.nodeType === NodeType.TEXT ||
      elementInfo.nodeType === NodeType.FORM_ITEM)
  ) {
    return { node: elementInfo, children: [] };
  }

  const children: WebElementNode[] = [];
  // For other elements (including containers that are not iframes)
  // or for nodes that didn't get elementInfo (like plain text nodes, comments)
  // iterate over childNodes of the DOM node.
  for (let i = 0; i < node.childNodes.length; i++) {
    logger('will dfs', node.childNodes[i]);
    const childNodeInfo = dfs(
      node.childNodes[i],
      currentWindow,
      currentDocument,
      elementInfo ? elementInfo.zoom : baseZoom, // Pass down calculated zoom of current node or parent's zoom
      basePoint, // basePoint is for the coordinate system of the current node's parent
    );
    if (childNodeInfo) {
      children.push(childNodeInfo);
    }
  }

  // If the current node itself had no collectible info, but it has processable children,
  // return a structure with node: null and those children.
  // Otherwise, if elementInfo is present, return it with its processed children.
  if (elementInfo || children.length > 0) {
    return { node: elementInfo, children };
  }

  return null; // Node is not visible, too small, or has no info and no processable children.
}

export function extractTreeNode(
  initNode: globalThis.Node,
  debugMode = true,
): WebElementNode | null { // Return type can be null if the root itself isn't processable
  setDebugMode(debugMode);
  console.log('[extractTreeNode] function called. debugMode:', debugMode, 'initNode:', initNode);
  indexId = 0;

  const topDoc = getTopDocument();
  const effectiveRootNode = initNode || (topDoc as unknown as Document).body; // Default to document.body with type assertion

  const tree = dfs(effectiveRootNode, window, document, 1, { left: 0, top: 0 });

  if (tree === null) {
    // This means dfs couldn't process effectiveRootNode (e.g. it was hidden/empty with no processable children)
    // To be consistent and not make Python receive a raw `null` which it logs as "no data",
    // let's return an empty tree structure. The AI should ideally see this as "empty page"
    // rather than "extraction failed".
    const emptyTree = { node: null, children: [] };
    if(debugMode) console.log('[extractTreeNode] Returning empty tree:', JSON.stringify(emptyTree));
    return emptyTree;
  }
  if(debugMode) console.log('[extractTreeNode] Returning tree:', descriptionOfTree(tree)); // Using descriptionOfTree for potentially large trees
  return tree;
}
