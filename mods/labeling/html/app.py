import streamlit as st
import json

st.title("Generated HTML Viewer and Rating Tool")

# Input area for the payload
payload_input = st.text_area("Paste the payload JSON here:", height=300)

if payload_input:
    try:
        # Remove triple backticks if present
        payload_str = payload_input.strip('`')
        
        # Load the JSON data
        payload = json.loads(payload_str)
        
        # Extract the conversation messages
        messages = payload.get("messages", [])
        
        st.header("Conversation History")
        for msg in messages:
            role = msg.get("role", "unknown").capitalize()
            content = msg.get("content", "")
            st.subheader(f"{role}:")
            st.write(content)
        
        # Extract the assistant's response
        assistant_content = payload["choices"][0]["message"]["content"]
        
        # Separate frontmatter and HTML content
        content_parts = assistant_content.split('---')
        if len(content_parts) >= 3:
            frontmatter = content_parts[1]
            html_code = '---'.join(content_parts[2:]).strip()
        else:
            html_code = assistant_content.strip()
        
        st.header("Assistant's Generated HTML")
        st.code(html_code, language='html')
        
        # Render the HTML
        st.header("Rendered HTML")
        st.components.v1.html(html_code, height=600, scrolling=True)
        
        # Rating interface
        st.header("Rate the Generated HTML")
        rating = st.radio("Select a rating:", [1, 2, 3, 4, 5], index=4)
        st.success(f"You rated this HTML: {rating}/5")
        
    except Exception as e:
        st.error(f"An error occurred: {e}")