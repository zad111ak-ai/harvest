"""
Shadow DOM — Extract content from Shadow DOM elements.

Many modern web components (React, Web Components, Lit) use Shadow DOM
which hides content from standard selectors. This module flattens
shadow trees to extract all visible text.

Usage:
    from harvest.shadow_dom import flatten_shadow_dom
    content = await flatten_shadow_dom(page)
"""

# JavaScript to recursively flatten shadow DOM trees
SHADOW_DOM_FLATTEN_JS = """
() => {
    function flattenShadowDOM(element) {
        let content = '';

        // Get shadow root if exists
        const shadowRoot = element.shadowRoot;
        if (shadowRoot) {
            const children = shadowRoot.querySelectorAll('*');
            children.forEach(child => {
                content += flattenShadowDOM(child);
            });
        }

        // Also check open mode shadow roots on children
        const regularChildren = element.querySelectorAll('*');
        regularChildren.forEach(child => {
            if (child.shadowRoot) {
                content += flattenShadowDOM(child);
            }
        });

        // Add element's own text content (only leaf nodes)
        if (element.children.length === 0 && element.textContent) {
            const text = element.textContent.trim();
            if (text) {
                content += text + '\\n';
            }
        }

        return content;
    }

    return flattenShadowDOM(document.body);
}
"""

# JavaScript to extract shadow DOM with structure
SHADOW_DOM_STRUCTURED_JS = """
() => {
    function extractStructured(element, depth = 0) {
        const result = {
            tag: element.tagName.toLowerCase(),
            text: '',
            children: [],
            hasShadow: !!element.shadowRoot
        };

        if (element.shadowRoot) {
            const shadowChildren = element.shadowRoot.querySelectorAll(':scope > *');
            shadowChildren.forEach(child => {
                result.children.push(extractStructured(child, depth + 1));
            });
        }

        const regularChildren = element.querySelectorAll(':scope > *');
        regularChildren.forEach(child => {
            if (!result.children.find(c => c.tag === child.tagName.toLowerCase())) {
                result.children.push(extractStructured(child, depth + 1));
            }
        });

        // Leaf nodes
        if (result.children.length === 0 && element.textContent) {
            result.text = element.textContent.trim();
        }

        return result;
    }

    return JSON.stringify(extractStructured(document.body));
}
"""


async def flatten_shadow_dom(page) -> str:
    """Extract all text content from shadow DOM elements.

    Args:
        page: Playwright page object

    Returns:
        Flattened text content from all shadow DOM trees
    """
    try:
        result = await page.evaluate(SHADOW_DOM_FLATTEN_JS)
        return result or ""
    except Exception:
        # Fallback: regular content
        return await page.content()


async def extract_shadow_dom_structured(page) -> dict:
    """Extract shadow DOM content with structure.

    Args:
        page: Playwright page object

    Returns:
        Structured dict with tag hierarchy and text content
    """
    import json

    try:
        result = await page.evaluate(SHADOW_DOM_STRUCTURED_JS)
        return json.loads(result) if result else {}
    except Exception:
        return {"tag": "body", "text": "", "children": [], "hasShadow": False}


async def has_shadow_dom(page) -> bool:
    """Check if page uses Shadow DOM.

    Args:
        page: Playwright page object

    Returns:
        True if any shadow roots are found
    """
    check_js = """
    () => {
        const elements = document.querySelectorAll('*');
        for (const el of elements) {
            if (el.shadowRoot) return true;
        }
        return false;
    }
    """
    try:
        return await page.evaluate(check_js)
    except Exception:
        return False
