import streamlit as st
from openai import OpenAI
from streamlit_chat import message
from datetime import datetime
from topics import get_random_topic_and_messages
from assign_conditions import get_even_assignment
import time
import random
import base64
import re

# model name from secrets (fallback for local testing)
MODEL_NAME = st.secrets.get("OPENAI_MODEL", "gpt-5.2")


# cache openai client across reruns
@st.cache_resource
def get_client():
    return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


# remove leading "name:" if the model adds it
def strip_name_prefix(text: str, names: list[str]) -> str:
    pattern = r"^(" + "|".join(re.escape(n) for n in names) + r")\s*:\s*"
    return re.sub(pattern, "", text, flags=re.IGNORECASE)


def render_chat():

    from utils import generate_participant_id
    from personas import generate_personas

    client = get_client()

    # ---------- session initialisation ----------
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "agent_rounds_raw" not in st.session_state:
        st.session_state.agent_rounds_raw = []

    if "reaction_times" not in st.session_state:
        st.session_state.reaction_times = []

    if "entered_chat" not in st.session_state:
        st.session_state.entered_chat = False

    if "user_count" not in st.session_state:
        st.session_state.user_count = 0

    if "trigger_ai_reply" not in st.session_state:
        st.session_state.trigger_ai_reply = False

    if "awaiting_post" not in st.session_state:
        st.session_state.awaiting_post = False

    if "avatar_data_uri" not in st.session_state:
        st.session_state.avatar_data_uri = {}

    # assign participant id
    if "participant_id" not in st.session_state:
        prolific_pid = st.session_state.get("prolific_pid", "testuser")
        if prolific_pid == "testuser":
            st.session_state.participant_id = f"test_{generate_participant_id()}"
        else:
            st.session_state.participant_id = prolific_pid

    # warning banner
    st.markdown(
        "<p style='color:red; font-weight:bold;'>⚠️ Please do not refresh the page. Refreshing will restart the study.</p>",
        unsafe_allow_html=True
    )

    # ---------- avatar helpers ----------
    def avatar_url(name):
        if name in st.session_state.avatar_data_uri:
            return st.session_state.avatar_data_uri[name]

        filename = st.session_state.avatar_map.get(name)
        if filename:
            try:
                with open(f"images/{filename}", "rb") as f:
                    encoded = base64.b64encode(f.read()).decode()
                uri = f"data:image/png;base64,{encoded}"
                st.session_state.avatar_data_uri[name] = uri
                return uri
            except FileNotFoundError:
                pass

        uri = f"https://api.dicebear.com/6.x/icons/svg?seed={name}"
        st.session_state.avatar_data_uri[name] = uri
        return uri

    def load_user_logo():
        with open("images/user.png", "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        return f"data:image/png;base64,{encoded}"


    # ---------- instruction page ----------
    if not st.session_state.entered_chat:
        st.subheader("Instructions")

        st.markdown("""
        <span style='color:#218838; font-weight:bold; font-size:17px;'>
        📌 Please imagine yourself as a new employee chatting in a real casual group with your new coworkers. Although your conversation partners are Generative AI agents, try to respond naturally as if they are real people in your workplace and you're truly part of this work environment. This will help us better understand communication in realistic settings.
        </span><br><br>

        Some of your colleagues have created a **casual chat group**. It is not a professional channel, but something they created to chat about anything from the weather to social gatherings, exchange ideas, or just everyday stuff.

        You've just been added to this group chat.
        When you enter, you’ll first see the last few messages that have already taken place.
        Feel free to jump in at any time.

        Please enter your name or nickname before joining.
        """, unsafe_allow_html=True)

        user_name = st.text_input("Enter your name or nickname (max 15 characters)")

        if user_name and len(user_name) <= 15:
            st.session_state.nickname = user_name

        if st.button("Enter Chat", disabled=not user_name or len(user_name) > 15):

            # assign ideology and topic using balanced assignment
            if "group_ideology" not in st.session_state:
                secret_dict = st.secrets["connections"]["gsheets"]
                ideology, topic = get_even_assignment(
                    st.session_state.participant_id,
                    secret_dict
                )
                st.session_state.group_ideology = ideology
                st.session_state.assigned_topic = topic

            # generate personas
            st.session_state.group_members, st.session_state.persona_dict, \
            st.session_state.trait_dict, st.session_state.avatar_map = \
                generate_personas(st.session_state.group_ideology)

            # load topic and preset messages
            topic_key, preset_messages = get_random_topic_and_messages(
                st.session_state.group_ideology,
                user_name,
                st.session_state.group_members,
                topic=st.session_state.assigned_topic
            )

            st.session_state.selected_topic = topic_key

            for speaker, line in preset_messages:
                st.session_state.messages.append({
                    "role": "assistant",
                    "speaker": speaker,
                    "content": line,
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "timestamp_unix": time.time(),
                    "temp_round_marker": True
                })

            st.session_state.user_logo = load_user_logo()
            st.session_state.entered_chat = True
            st.rerun()

        return


    # ---------- main chat ui ----------
    st.subheader("Group Chat 💬")
    group_members = st.session_state.group_members
    st.markdown(f"👥 **Members:** {', '.join(group_members)} and **You**")

    # display messages
    for i, msg in enumerate(st.session_state.messages):
        is_user = msg["role"] == "user"
        logo = st.session_state.user_logo if is_user else avatar_url(msg["speaker"])
        name = "You" if is_user else msg["speaker"]

        dt = datetime.strptime(msg["timestamp"], "%H:%M:%S")
        clean_time = dt.strftime("%H:%M")

        message(
            f"**{name}:** {msg['content']}\n\n<i style='color:gray; font-size:0.8em;'>{clean_time}</i>",
            is_user=is_user,
            key=f"msg_{i}",
            logo=logo,
            allow_html=True
        )

    # ---------- user input ----------
    user_input = st.chat_input("Type your message here...")
    if user_input:

        now = time.time()

        assistant_times = [
            m["timestamp_unix"]
            for m in reversed(st.session_state.messages)
            if m["role"] == "assistant"
        ]
        reaction_sec = now - assistant_times[0] if assistant_times else ""
        st.session_state.reaction_times.append(reaction_sec)

        st.session_state.messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "timestamp_unix": now
        })

        st.session_state.user_count += 1

        if st.session_state.user_count >= 5:
            st.session_state.awaiting_post = True
        else:
            st.session_state.trigger_ai_reply = True

        st.rerun()


    # ---------- ai responses ----------
    if st.session_state.trigger_ai_reply:
        st.session_state.trigger_ai_reply = False

        # select responders
        num_responders = random.randint(1, 3)
        ai_names = random.sample(group_members, k=num_responders)

        for i, ai_name in enumerate(ai_names):

            # stagger typing start
            if i == 0:
                time.sleep(0.8)
            else:
                time.sleep(random.uniform(0.2, 0.4))

            with st.spinner(f"{ai_name} is typing{'.' * random.randint(1, 3)}"):
                # typing duration
                time.sleep(random.uniform(1.8, 2.8))

                trait = st.session_state.trait_dict[ai_name]
                lowercase_instruction = (
                    "use all lowercase like casual texting."
                    if trait in ["HO", "LC"]
                    else "use normal sentence casing."
                )

            
            # extract topic and agent ideology for buildign the system prompt
            topic = st.session_state.selected_topic
            ideology = st.session_state.group_ideology

            system_block = {
                "role": "system",
                "content": (
                    f"{st.session_state.persona_dict[ai_name]} "
                    f"The main ongoing discussion topic in this chat is: {topic}. "
                    f"You are {ai_name} in a casual coworker group chat. "
                    f"{lowercase_instruction}.  This rule applies only if your trait is listed as HO or LC. " 
                    "Do not repeat what others already said. "
                    "If the question was answered, react briefly or add a new angle. "
                    "Stay on topic and build on the conversation. "
                    f"Stay aligned with your {ideology} leaning. "
                    "Keep replies to 1–2 short sentences. "
                    "Do not lecture, summarise, or sound like an assistant. "
                    "Write your reply with a different opening phrase from the previous speaker. "
                    "Do not speak for the group or say 'we'. "
                    "Chat history shows who said what as 'name: message'. "
                )
            }

            context_blocks = []
            for m in st.session_state.messages:
                if m["role"] == "user":
                    context_blocks.append({"role": "user", "content": m["content"]})
                else:
                    context_blocks.append({
                        "role": "assistant",
                        "content": f"{m['speaker']}: {m['content']}"
                    })

            resp = client.responses.create(
                model=MODEL_NAME,
                input=[system_block] + context_blocks
            )

            # cleanup
            raw = resp.output_text.strip()
            raw = raw.replace("—", "...")
            reply = strip_name_prefix(raw, group_members)


            timestamp = datetime.now().strftime("%H:%M:%S")
            display_time = datetime.now().strftime("%H:%M")

            message(
                f"**{ai_name}:** {reply}\n\n<i style='color:gray; font-size:0.8em;'>{display_time}</i>",
                is_user=False,
                key=f"ai_msg_{len(st.session_state.messages)}_{ai_name}",
                logo=avatar_url(ai_name),
                allow_html=True
            )

            st.session_state.messages.append({
                "role": "assistant",
                "speaker": ai_name,
                "content": reply,
                "timestamp": timestamp,
                "timestamp_unix": time.time(),
                "temp_round_marker": True
            })


        # ---------- FOLLOW-UP AGENT (one more nudge back to participant) ----------
        # pick a follow-up speaker who did not just speak
        last_speaker = ai_names[-1]
        followup_candidates = [n for n in group_members if n != last_speaker]
        followup_speaker = random.choice(followup_candidates)

        trait = st.session_state.trait_dict[followup_speaker]
        lowercase_instruction = (
            "use all lowercase like casual texting."
            if trait in ["HO", "LC"]
            else "use normal sentence casing."
        )

        topic = st.session_state.selected_topic
        ideology = st.session_state.group_ideology

        system_block = {
            "role": "system",
            "content": (
                f"{st.session_state.persona_dict[followup_speaker]} "
                f"The main ongoing discussion topic in this chat is: {topic}. "
                f"You generally lean {ideology}. "
                f"You are {followup_speaker}, chatting casually with coworkers. "
                "Add one short, natural follow-up that keeps the conversation moving. "
                "Write your reply with a different opening phrase from the previous speaker. "
                "You may ask the participant one short, casual question. "
                "Do not repeat what others already said. "
                "If the topic drifted, gently relate it back to the main topic. "
                "Do not lecture or summarise. "
                "Do not speak for the group or say 'we'. "
            )
        }

        context_blocks = []
        for m in st.session_state.messages:
            if m["role"] == "user":
                context_blocks.append({"role": "user", "content": m["content"]})
            else:
                context_blocks.append({
                    "role": "assistant",
                    "content": f"{m['speaker']}: {m['content']}"
                })


        with st.spinner(f"{followup_speaker} is typing..."):
            time.sleep(random.uniform(1.5, 2.5))

            resp = client.responses.create(
                model=MODEL_NAME,
                input=[system_block] + context_blocks,
                max_output_tokens=120
            )


        # cleanup
        raw = resp.output_text.strip()
        raw = raw.replace("—", "...")
        reply = strip_name_prefix(raw, group_members)


        timestamp = datetime.now().strftime("%H:%M:%S")
        display_time = datetime.now().strftime("%H:%M")

        message(
            f"**{followup_speaker}:** {reply}\n\n<i style='color:gray; font-size:0.8em;'>{display_time}</i>",
            is_user=False,
            key=f"ai_msg_{len(st.session_state.messages)}_{followup_speaker}",
            logo=avatar_url(followup_speaker),
            allow_html=True
        )

        st.session_state.messages.append({
            "role": "assistant",
            "speaker": followup_speaker,
            "content": reply,
            "timestamp": timestamp,
            "timestamp_unix": time.time(),
            "temp_round_marker": True
        })


    # ---------- end ----------
    if st.session_state.awaiting_post:
        st.markdown("*That is the end of the study.*")
        time.sleep(1)  # gives user a moment
        st.session_state.page = "post"
        st.session_state.awaiting_post = False

        # collect and store current round's replies only
        round_text = [
            f"{m['speaker']}: {m['content']}"
            for m in st.session_state.messages
            if m.get("temp_round_marker") and m["role"] == "assistant"
        ]

        if round_text:
            st.session_state.agent_rounds_raw.append("\n".join(round_text))

        for m in st.session_state.messages:
            m.pop("temp_round_marker", None)

        st.rerun()    