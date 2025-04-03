import streamlit as st
import pandas as pd
import time
import datetime
import random
import os
from google.oauth2 import service_account
import json

# Set up the Streamlit page configuration
st.set_page_config(page_icon="📷", page_title="PictoPercept", layout="centered", initial_sidebar_state="collapsed")
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize user ID and DataFrame if not already in session
if "userid" not in st.session_state:
    if "choice_respondent" in st.query_params:
        st.session_state.userid = str(st.query_params.choice_respondent)
    else:
        st.session_state.userid = "anonymous_" + str(random.randint(10000, 99999))

st.sidebar.info("userid: " + st.session_state.userid)

# Initialize responses DataFrame if not already in session
if "responses_df" not in st.session_state:
    st.session_state.responses_df = pd.DataFrame(columns=['userid', 'item', 'file', 'chosen', 'timestamp', 'attention_check'])

# Initial state to track if consent has been given
if "consent_given" not in st.session_state:
    st.session_state.consent_given = False

# Function to get all neutral face images from CFD dataset
def get_cfd_images():
    image_paths = []
    base_path = "./CFD_dataset/Images/CFD"  # Adjusted path
    for root, dirs, files in os.walk(base_path):
        for file in files:
            if file.endswith("-N.jpg"):  # Neutral expression images
                full_path = os.path.join(root, file)
                image_paths.append(full_path)
    return image_paths

# Consent button
if not st.session_state.consent_given:
    st.title("📷 PictoPercept")
    st.write("&nbsp;")

    col1_land, col2_land = st.columns([1, 1.618])

    with col1_land:
        with st.container(border=True):
            # Find and display the first neutral face image
            example_images = get_cfd_images()
            if example_images:
                st.image(example_images[0])
            else:
                st.error("No images found in CFD dataset! Check your path.")
    with col2_land:
        st.write("""
            We will show you two images at a time, and ask who you a question related to the shown occupation. 
            You must choose one person, and their picture is the only information you have. 
            Your responses are anonymous, and the survey lasts 1 minute.

            Trust your instincts!
            """)
    
    st.write("&nbsp;")
    if st.button("Let us begin!", type="primary", use_container_width=True):
        st.session_state.consent_given = True
        st.rerun()

if st.session_state.consent_given:
    
    if "data" not in st.session_state:
        # Get all neutral face images
        all_images = get_cfd_images()
        if not all_images:
            st.error("No images found in CFD dataset! Check your path.")
            st.stop()
            
        # Create a DataFrame with the image paths
        df = pd.DataFrame({'file': all_images})
        df = df.sample(frac=1).reset_index(drop=True)  # shuffle rows
        
        st.session_state.data = df
        st.session_state.index = 0
        st.session_state.start_time = datetime.datetime.now()
        # Select the last pair of images for the attention check
        st.session_state.attention_check_pair = st.session_state.data.iloc[-2:]
    
    ### Rest of your original code continues unchanged from here ###
    ### Randomization of progress bar and timer ###
    if "show_timer_progress" not in st.session_state:
        st.session_state.show_timer_progress = random.choice([True, False])

    ### Exit button ###
    time_elapsed = datetime.datetime.now() - st.session_state.start_time
    if time_elapsed.total_seconds() > 65 and len(st.session_state.responses_df) >= 2:
        
        # Write to db here
        recordlist = st.session_state.responses_df.to_dict(orient='records')

        progress_bar = st.progress(0)
        status_text = st.empty()

        for idx, record in enumerate(recordlist):
            write_to_firestore(record)
            progress = (idx + 1) / len(recordlist)
            progress_bar.progress(progress)
            status_text.text(f"Saving your responses: {int(progress * 100)}%")
        
        # Completion message
        status_text.text("All done!")
        st.write("&nbsp;")
        with st.expander("Wish to view your data?"):
            st.info("This is _not_ shown during a real survey.")
            
            df2 = pd.merge(st.session_state.responses_df, st.session_state.data, on='file', how='inner')
            st.dataframe(df2)
                
    else:
        st.write("&nbsp;")

        # Determine if we are at an attention check
        current_index = st.session_state.index
        if current_index == 4:  # Attention check at iteration 3
            image1 = st.session_state.attention_check_pair.iloc[0]["file"]
            image2 = st.session_state.attention_check_pair.iloc[1]["file"]
            is_attention_check = True
        elif current_index == 18:  # Attention check at iteration 10
            image1 = st.session_state.attention_check_pair.iloc[1]["file"]
            image2 = st.session_state.attention_check_pair.iloc[0]["file"]
            is_attention_check = True
        elif current_index == 40:  # Attention check at iteration 21
            image1 = st.session_state.attention_check_pair.iloc[0]["file"]
            image2 = st.session_state.attention_check_pair.iloc[1]["file"]
            is_attention_check = True
        else:  # Normal rounds
            image1 = st.session_state.data.iloc[current_index]["file"]
            image2 = st.session_state.data.iloc[current_index + 1]["file"]
            is_attention_check = False

        st.write("Who of these looks like a xx?")
        
        def save_response(selected):
            current_time = datetime.datetime.now()
            st.session_state.responses_df = pd.concat([
                st.session_state.responses_df,
                pd.DataFrame([
                    {
                        'userid': st.session_state.userid,
                        'item': (current_index // 2) + 1,
                        'file': image1,
                        'chosen': selected == 1,
                        'timestamp': current_time.strftime("%Y-%m-%d %H:%M:%S"),
                        'show_timer_progress': st.session_state.show_timer_progress,
                        'attention_check': is_attention_check
                    },
                    {
                        'userid': st.session_state.userid,
                        'item': (current_index // 2) + 1,
                        'file': image2,
                        'chosen': selected == 2,
                        'timestamp': current_time.strftime("%Y-%m-%d %H:%M:%S"),
                        'show_timer_progress': st.session_state.show_timer_progress,
                        'attention_check': is_attention_check
                    }
                ])
            ], ignore_index=True)
            st.session_state.index += 2

        ### Main Buttons Display ###
        with st.container(border=True):
            col1, col2 = st.columns(2, gap="large")
            with col1:
                button1 = st.button(
                    "Person 1", type="primary", key="btn1", on_click=save_response, args=[1], use_container_width=True
                )
            with col2:
                button2 = st.button(
                    "Person 2", type="primary", key="btn2", on_click=save_response, args=[2], use_container_width=True
                )
            
            col1.image(image1, use_container_width="always")
            col2.image(image2, use_container_width="always")

        st.write("&nbsp;")
        
        if st.session_state.show_timer_progress:
            progress_bar = st.progress(0, text = "⏰ Try to answer as fast as possible.")
            for i in range(1, 6):
                if i == 1:
                    time.sleep(1)
                    progress_text = "⏰ Try to answer as fast as possible. Time taken: 1 second"
                elif i == 5:
                    progress_text = ":red[⏰ Try to answer as fast as possible. Time taken: More than 5 seconds!]"
                else:
                    progress_text = "⏰ Try to answer as fast as possible. Time taken: " + str(i) + " seconds"
                progress_bar.progress(i * 20, text=progress_text)
                time.sleep(1)