import streamlit as st
import requests as r
import json
import asyncio
import aiohttp
import webbrowser
import PyPDF2
from io import BytesIO
from PyPDF2 import PdfMerger

async def async_get(url, headers):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            return await response.text()

async def async_post(url, headers, json_data):
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=json_data) as response:
            return await response.text()

def authenticate(token):
    head = {
        "Authorization": f"Bearer {token}",
        "Referer": "https://tesseractonline.com/"
    }
    response = r.get("https://api.tesseractonline.com/studentmaster/subjects/4/6", headers=head).text
    data = json.loads(response)
    if data['Error'] == False:
        return head
    else:
        st.error('The given token is expired or may be wrong.')
        return None

@st.cache_data
def get_dashboard(head):
    url = "https://api.tesseractonline.com/studentmaster/subjects/4/6"
    response = r.get(url, headers=head).text
    subjects = json.loads(response)['payload']
    return {subject['subject_id']: subject['subject_name'] for subject in subjects}

@st.cache_data
def get_units(subject_id, head):
    url = f"https://api.tesseractonline.com/studentmaster/get-subject-units/{subject_id}"
    response = r.get(url, headers=head).text
    units = json.loads(response)['payload']
    return {unit['unitId']: unit['unitName'] for unit in units}

@st.cache_data
def get_topics(unit_id, head):
    url = f"https://api.tesseractonline.com/studentmaster/get-topics-unit/{unit_id}"
    response = r.get(url, headers=head).text
    topics = json.loads(response)['payload']['topics']
    return {
        f"{topic['id']}. {topic['name']}  {topic['learningFlag']}": {
            'pdf': f"https://api.tesseractonline.com/{topic['pdf'].lstrip('/')}",
            'video': topic['videourl']
        } for topic in topics
    }

def merge_pdfs(pdf_urls):
    merger = PdfMerger()
    for url in pdf_urls:
        try:
            response = r.get(url)
            response.raise_for_status()  # Check for HTTP errors
            pdf = BytesIO(response.content)
            merger.append(pdf)
        except r.RequestException as e:
            st.error(f"Failed to fetch PDF from {url}. Error: {e}")
        except PyPDF2.utils.PdfReadError as e:
            st.error(f"Failed to read PDF from {url}. Error: {e}")
    
    output = BytesIO()
    try:
        merger.write(output)
        merger.close()
        output.seek(0)  # Reset buffer position to the beginning
    except Exception as e:
        st.error(f"Failed to merge PDFs. Error: {e}")
    
    return output

async def write_quiz(i, head):
    try:
        quiz_data = json.loads(await async_get(f"https://api.tesseractonline.com/quizattempts/create-quiz/{i}", head))
        quiz_id = quiz_data["payload"]['quizId']
        questions = quiz_data["payload"]["questions"]
        options = ['a', 'b', 'c', 'd']
        previous_score = json.loads(await async_post(
            "https://api.tesseractonline.com/quizattempts/submit-quiz",
            head,
            {
                "branchCode": "NGIT-CSM",
                "sectionName": "NGIT-CSM-PS1",
                "quizId": f'{quiz_id}'
            }
        ))["payload"]["score"]
        
        st.write("Work in progress, please wait...")
        for question in questions:
            for option in options:
                await async_post(
                    "https://api.tesseractonline.com/quizquestionattempts/save-user-quiz-answer",
                    head,
                    {
                        "quizId": f'{quiz_id}',
                        "questionId": f"{question['questionId']}",
                        "userAnswer": f'{option}'
                    }
                )
                score = json.loads(await async_post(
                    "https://api.tesseractonline.com/quizattempts/submit-quiz",
                    head,
                    {
                        "branchCode": "NGIT-CSM",
                        "sectionName": "NGIT-CSM-PS1",
                        "quizId": f'{quiz_id}'
                    }
                ))["payload"]["score"]
                if score == 5:
                    st.success('Test completed, refresh the page.')
                    return
                if score > previous_score:
                    previous_score = score
                    break
    except KeyError:
        st.error('This subject or topic is inactive.')

async def write_quiz_for_all_topics(selected_topics, head):
    for topic in selected_topics:
        await write_quiz(topic.split('.')[0], head)

def get_all_units_pdfs(subject_id, head):
    """Fetch all PDF links for every topic in all units of a subject."""
    units = get_units(subject_id, head)
    pdf_links = []
    for unit_id in units.keys():
        topics = get_topics(unit_id, head)
        for topic in topics.values():
            if topic.get('pdf'):
                pdf_links.append(topic['pdf'])
    return pdf_links

def get_all_unit_topics(subject_id, head):
    """Fetch topics from all units for a given subject."""
    units = get_units(subject_id, head)
    unit_topics = {}
    for unit_id, unit_name in units.items():
        topics = get_topics(unit_id, head)
        unit_topics[unit_name] = topics
    return unit_topics

# def main():
#     st.title('Tesseract Quiz Automation')

#     token = st.text_input('Enter token:', type='password')
#     if token:
#         head = authenticate(token)
#         if head:
#             subjects = get_dashboard(head)
#             subject_choice = st.selectbox('Select subject:', list(subjects.values()))

#             if subject_choice:
#                 subject_id = list(subjects.keys())[list(subjects.values()).index(subject_choice)]
#                 unit_topics = get_all_unit_topics(subject_id, head)
                
#                 all_selected_pdfs = []
#                 for unit_name, topics in unit_topics.items():
#                     st.subheader(f"Unit: {unit_name}")
#                     topic_keys = list(topics.keys())
#                     selected_topics = st.multiselect(f"Select topics from {unit_name}:", topic_keys, default=topic_keys)
                    
#                     for selected_topic in selected_topics:
#                         # Ensure the selected topic has a valid PDF link and append it to the list
#                         if topics[selected_topic].get('pdf'):
#                             all_selected_pdfs.append(topics[selected_topic]['pdf'])

#                 if all_selected_pdfs:
#                     if st.button('Merge Selected PDFs'):
#                         merged_pdf = merge_pdfs(all_selected_pdfs)
#                         st.download_button(
#                             label="Download Merged PDF",
#                             data=merged_pdf.getvalue(),
#                             file_name=f"{subject_choice}_merged.pdf",
#                             mime="application/pdf"
#                         )
#                 else:
#                     st.warning("No PDFs selected.")
   
def main():
    st.title('Tesseract PDF makers')

    token = st.text_input('Enter token:', type='password')
    if token:
        head = authenticate(token)
        if head:
            subjects = get_dashboard(head)
            subject_choice = st.selectbox('Select subject:', list(subjects.values()))

            if subject_choice:
                subject_id = list(subjects.keys())[list(subjects.values()).index(subject_choice)]
                unit_topics = get_all_unit_topics(subject_id, head)
                
                # Only show units with available topics and PDFs
                available_units = {
                    unit_name: {topic: details for topic, details in topics.items() if details.get('pdf')}
                    for unit_name, topics in unit_topics.items()
                    if any(details.get('pdf') for details in topics.values())
                }

                if not available_units:
                    st.warning("No available units or PDFs for the selected subject.")
                    return

                all_selected_pdfs = []
                for unit_name, topics in available_units.items():
                    st.subheader(f"Unit: {unit_name}")
                    topic_keys = list(topics.keys())
                    selected_topics = st.multiselect(f"Select topics from {unit_name}:", topic_keys, default=topic_keys)
                    
                    for selected_topic in selected_topics:
                        # Add only valid PDF links to the list
                        if topics[selected_topic].get('pdf'):
                            all_selected_pdfs.append(topics[selected_topic]['pdf'])

                if all_selected_pdfs:
                    if st.button('Merge Selected PDFs'):
                        merged_pdf = merge_pdfs(all_selected_pdfs)
                        st.download_button(
                            label="Download Merged PDF",
                            data=merged_pdf.getvalue(),
                            file_name=f"{subject_choice}_merged.pdf",
                            mime="application/pdf"
                        )
                else:
                    st.warning("No PDFs selected.")
                   
if __name__ == "__main__":
    main()



