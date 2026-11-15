import bleach

def sanitize_ckeditor_html(html_content):
    """
    Cleans HTML from CKEditor to prevent XSS attacks.
    Allows safe formatting tags but blocks <script>, <iframe>, onerror, etc.
    """
    if not html_content:
        return html_content

    allowed_tags = [
        'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'strike', 's', 'del',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'blockquote', 'a',
        'table', 'thead', 'tbody', 'tr', 'th', 'td',
        'img', 'figure', 'figcaption', 'span', 'div'
    ]

    allowed_attributes = {
        'a': ['href', 'title', 'target', 'rel'],
        'img': ['src', 'alt', 'title', 'width', 'height'],
        'span': ['style'],
        'p': ['style'],
        'div': ['style'],
        'td': ['colspan', 'rowspan'],
        'th': ['colspan', 'rowspan'],
    }

    cleaned_html = bleach.clean(
        html_content,
        tags=allowed_tags,
        attributes=allowed_attributes,
        protocols=['http', 'https', 'mailto'], 
        strip=True 
    )
    
    return cleaned_html