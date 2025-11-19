import streamlit as st
from openai import OpenAI
from streamlit_chat import message
from datetime import datetime
from topics import get_random_topic_and_messages
import time
import random
import base64
from assign_conditions import get_even_assignment

import re

def strip_name_prefix(text: str, names: list[str]) -> str:
    """Remove any leading '<name>:' in any case, including extra whitespace."""
    pattern = r"^(" + "|".join(re.escape(n) for n in names) + r")\s*:\s*"
    return re.sub(pattern, "", text, flags=re.IGNORECASE)




if "agent_rounds_raw" not in st.session_state:
    st.session_state.agent_rounds_raw = []



def render_chat():
    # import streamlit.components.v1 as components
    if "agent_rounds_raw" not in st.session_state:
        st.session_state.agent_rounds_raw = []

    from utils import generate_participant_id

    if "participant_id" not in st.session_state:
        prolific_pid = st.session_state.get("prolific_pid", "testuser")
        if prolific_pid == "testuser":
            st.session_state.participant_id = f"test_{generate_participant_id()}"
        else:
            st.session_state.participant_id = prolific_pid




    # warning banner
    st.markdown(
        "<p style='color:red; font-weight:bold;'>⚠️ Please do not refresh the page. Doing so will restart the study and erase your answers.</p>",
        unsafe_allow_html=True
    )


    if "awaiting_post" not in st.session_state:
        st.session_state.awaiting_post = False


    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


    # --- session initiation ---
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "entered_chat" not in st.session_state:
        st.session_state.entered_chat = False
    if "user_logo" not in st.session_state:
        st.session_state.user_logo = ""
    if "user_count" not in st.session_state:
        st.session_state.user_count = 0
    if "trigger_ai_reply" not in st.session_state:
        st.session_state.trigger_ai_reply = False


    # --- AI agents utilities ---
    # randomly pick 10 personas, assign big 5 styles, and select 3 for chat
    from personas import generate_personas

    if "group_ideology" not in st.session_state:
        secret_dict = st.secrets["connections"]["gsheets"]

        assigned_ideology, assigned_topic = get_even_assignment(
            st.session_state.participant_id,
            secret_dict
        )
        st.session_state.group_ideology = assigned_ideology
        st.session_state.assigned_topic = assigned_topic





    def avatar_url(name):
        filename = st.session_state.avatar_map.get(name)
        if filename:
            try:
                with open(f"images/{filename}", "rb") as f:
                    encoded = base64.b64encode(f.read()).decode()
                return f"data:image/png;base64,{encoded}"
            except FileNotFoundError:
                pass
        return f"https://api.dicebear.com/6.x/icons/svg?seed={name}"


    def load_user_logo():
        with open("images/user.png", "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        return f"data:image/png;base64,{encoded}"



    # --- instruction page ---
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

        user_name = st.text_input("Enter your name or nickname (max 15 characters)", key="nickname_input")

        if user_name:
            if len(user_name) > 15:
                st.warning("Nickname must be 15 characters or fewer.")
            else:
                st.session_state.nickname = user_name
        
        if st.button("Enter Chat", disabled=not user_name or len(user_name) > 15):
            # assign liberal or conservative group
            if "group_ideology" not in st.session_state:
                st.session_state.group_ideology = random.choice(["liberal", "conservative"])
            

            # generate personas
            if "group_members" not in st.session_state:
                st.session_state.group_members, st.session_state.persona_dict, st.session_state.trait_dict, st.session_state.avatar_map = generate_personas(st.session_state.group_ideology)


            # get one topic and its messages
            # also passes 3 agent names randomly selected
            topic_key, preset_messages = get_random_topic_and_messages(
                st.session_state.group_ideology,
                user_name,
                st.session_state.group_members,
                topic=st.session_state.assigned_topic  # force balanced topic
            )

            st.session_state.selected_topic = topic_key

            for speaker, line in preset_messages:
                st.session_state.messages.append({
                    "role": "assistant",
                    "speaker": speaker,
                    "content": line,
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "timestamp_unix": time.time()
                })

            st.session_state.user_logo = load_user_logo()
            st.session_state.entered_chat = True
            st.rerun()



    # --- main chat UI ---
    else:
        st.subheader("Group Chat Begins 💬")
        group_members = st.session_state.group_members
        st.markdown(f"👥 **Members:** {', '.join(group_members)} and **You**")


        # SHOW ALL MESSAGES
        for i, msg in enumerate(st.session_state.messages):
            is_user = msg["role"] == "user"
            logo = st.session_state.user_logo if is_user else avatar_url(msg["speaker"])
            name = "You" if is_user else msg["speaker"]

            #for display only the h and m
            try:
                dt = datetime.strptime(msg["timestamp"], "%H:%M:%S")
            except ValueError:
                dt = datetime.strptime(msg["timestamp"], "%H:%M")

            clean_timestamp = dt.strftime("%H:%M")

            timestamp = f"<i style='color:gray; font-size: 0.8em;'>{clean_timestamp}</i>"


            message(
                f"**{name}:** {msg['content']}\n\n{timestamp}",
                is_user=is_user,
                key=f"msg_{i}",
                logo=logo,
                allow_html=True
            )





        #### USER INPUT (participant input) ####
        # store reaction time using unix timestamp
        user_input = st.chat_input("Type your message here...")
        if user_input:

            st.session_state.round_id = st.session_state.get("round_id", 0) + 1
            st.session_state.round_has_question = False
    

            now = time.time()  # record current time in Unix timestamp

            # find last assistant message timestamp
            assistant_times = [
                m["timestamp_unix"]
                for m in reversed(st.session_state.messages)
                if m["role"] == "assistant" and "timestamp_unix" in m
            ]
            if assistant_times:
                reaction_sec = now - assistant_times[0]
            else:
                reaction_sec = ""

            # save reaction time
            if "reaction_times" not in st.session_state:
                st.session_state.reaction_times = []
            st.session_state.reaction_times.append(reaction_sec)

            # save user message with both readable and unix timestamp
            st.session_state.messages.append({
                "role": "user",
                "content": user_input,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "timestamp_unix": now
            })




            # make sure response1 is the part of round 1
            if st.session_state.user_count == 0:
                st.session_state.messages[-1]["temp_round_marker"] = True


            # collect and store the previous round's AI responses before clearing
            round_text = [
                f"{m['speaker']}: {m['content']}"
                for m in st.session_state.messages
                if m.get("temp_round_marker") and m["role"] == "assistant"
            ]
            if round_text:
                st.session_state.agent_rounds_raw.append("\n".join(round_text))

            # now clear the temp_round_marker for the new round
            for m in st.session_state.messages:
                m.pop("temp_round_marker", None)


            st.session_state.user_count += 1

            # check if it is the 5th time BEFORE any AI agent replies
            if st.session_state.user_count >= 5:
                st.session_state.awaiting_post = True
                st.rerun()
            else:
                st.session_state.trigger_ai_reply = True
                st.rerun()


        # AI agent response
        if st.session_state.trigger_ai_reply and st.session_state.user_count <= 6:
            st.session_state.trigger_ai_reply = False

            #detect if someone was called by name
            def get_called_name(messages, members):
                import re
                for m in reversed(messages[-3:]):  # check last 3 messages
                    if m["role"] == "user":
                        source = m["content"]
                    elif m["role"] == "assistant" and m.get("speaker") not in members:
                        source = m["content"]
                    else:
                        continue
                    for name in members:
                        pattern = re.compile(rf"\b{name}\b", re.IGNORECASE)
                        if pattern.search(source):
                            return name
                return None

            
            
            time.sleep(random.uniform(0.8, 1.0))

            # choose responders without heavy inference (fast response)
            called_name = get_called_name(st.session_state.messages, group_members)
            if called_name in group_members:
                ai_names = [called_name]
            else:
                num_responders = random.randint(1, 3)
                ai_names = random.sample(group_members, k=num_responders)



            # loop
            ##### REGULAR AI RESPONSE BLOCK ####
            for i, ai_name in enumerate(ai_names):
                # 1 second before the first spinner only
                if i == 0:
                    time.sleep(1.0)
                else:
                    time.sleep(random.uniform(0.1, 0.3))

                with st.spinner(f"{ai_name} is typing{'.' * random.randint(1, 3)}"):
                    # shorter "typing" time for later agents
                    time.sleep(random.uniform(0.4, 0.7))


                    trait = st.session_state.trait_dict[ai_name]

                    # lowercase rule for only HP and LC
                    if trait in ["HO", "LC"]:
                        lowercase_instruction = "Use all lowercase, like someone texting casually."
                    else:
                        lowercase_instruction = "Use normal sentence casing (capitalise sentences and 'I')."

                
                    # build system + context blocks
                    system_block = {
                        "role": "system",
                        "content": (
                            f"{st.session_state.persona_dict[ai_name]} "
                            f"You are {ai_name}, one of several new coworkers chatting casually in a small workplace group chat. "
                            f"{lowercase_instruction}.  This rule applies only if your trait is listed as HO or LC. " 
                            "Speak only as yourself. Do not speak for the group or refer to others as 'we'. "
                            "Keep replies nautral, sometimes a quick 1–2 sentence comment (~20–40 words), other times a fuller 3–4 sentence message (~60–80 words)."
                            "Write like a real person texting in a group chat: mix short sentences, contractions, filler words, and natural rhythm. "
                            "Don’t sound like you’re explaining or summarising facts; react, agree, joke lightly, or add personal takes. "
                            "Each coworker should only respond if they have something new to add; if others have already covered the same point, react briefly or acknowledge them instead of restating their view."
                            "You can mention feelings or personal examples, but keep them realistic and consistent with your persona. "
                            "Don’t use bullet points, don’t list data, don’t paste links, and don’t act like a teacher or assistant. "
                            "Do not ask the participant a direct question in this message. "
                            "Never say things like 'I can share resources' or 'I can drop summaries'. "
                            "Do not change topics unless the participant insists so. "
                            "Stay focused on the current topic and build on what others said. "
                            "Maintain your ideological stance. Acknowledge differing views if needed, but do not shift your position. "
                            "Mimic how real people type, including slight disfluencies (like 'um', 'I guess', 'I mean'). "
                            "Vary the length and tone of your replies, sometimes short, sometimes more expressive. "
                            "Do not mention you're an AI or use overly formal language."
                            "Keep it conversational and spontaneous. "
                            "Stay roughly aligned with your ideological leaning, but make it sound like normal opinions, not slogans."
                            "Each line in the history clearly shows who said it. "
                            "Never repeat someone else's message or speak as them."
                        )
                    }

                    context_blocks = []
                    for m in st.session_state.messages:
                        if m["role"] == "user":
                            context_blocks.append({"role": "user", "content": m["content"]})
                        else:
                            context_blocks.append({"role": "assistant", "content": f"{m['speaker']}: {m['content']}"})

    

                    # first pass
                    resp = client.responses.create(
                        model="gpt-5.1",
                        input=[system_block] + context_blocks
                    )





                    reply = resp.output_text.strip()

                    # after first pass, before cleanup/render
                    recent_ai_texts = [m["content"] for m in st.session_state.messages if m["role"] == "assistant"][-10:]
                    if reply in recent_ai_texts:
                        resp = client.responses.create(
                            model="gpt-5.1",
                            input=[{"role": "system", "content": "Avoid repeating yourself; add a new angle briefly."}]
                                + [system_block] + context_blocks
                        )
                        reply = resp.output_text.strip()

                    # cleanup
                    reply = reply.replace("—", "...")
                    reply = strip_name_prefix(reply, group_members)



                    # render + store
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    display_time = datetime.now().strftime("%H:%M")
                    message(
                        f"**{ai_name}:** {reply}\n\n<i style='color:gray; font-size: 0.8em'>{display_time}</i>",
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




            # END of 1-3 agents' replies → do 1 more follow-up
            # get last agent speaker (the final agent who replied)
            last_assistant = None
            for m in reversed(st.session_state.messages):
                if m["role"] == "assistant":
                    last_assistant = m["speaker"]
                    break

            # make sure the follow-up speaker is not the last assistant
            followup_candidates = [name for name in group_members if name != last_assistant]
            followup_speaker = random.choice(followup_candidates)

            time.sleep(0.1)

    


            with st.spinner(f"{followup_speaker} is typing..."):
                time.sleep(random.uniform(0.3, 0.5))

                user_name = st.session_state.get("nickname", "you")

                style = ""
                allow_question = not st.session_state.round_has_question
                question_rule = ("If you ask a question, keep it to ONE short question at the end. "
                                "If anyone already asked a question this round, ask NONE.")
                if not allow_question:
                    question_rule = "Do NOT ask any questions in this message."


                followup_prompt = (
                    f"{st.session_state.persona_dict[followup_speaker]} "
                    f"You are {followup_speaker} in a casual chat group between colleagues. "
                    f"{question_rule} "
                    "Add one short, natural comment that keeps the conversation moving. "
                    "Sound human, not robotic or instructive—use contractions, natural pauses, or mild emotion. "
                    "Don’t lecture, explain, or list information. "
                    "Just react naturally, add a thought, joke, or short reflection depending on your personality. "
                    "Speak only as yourself. Do not represent the group or refer to others as 'we'. "
                    "Be casual and brief, and vary your tone and length like real people. "
                    "Avoid sounding robotic or formulaic. Do not use em dashes (—). "
                    "Mimic how real people type."
                    "If the user changes the topic, gently steer it back on topic, but if the user still wants to change topic, then go with it."
                    "Maintain your ideological stance. You can acknowledge differing views politely, but do not shift your position. "
                    "Do not invent any other names outside this group."
                    f"{style}"
                )



                system_block = {"role": "system", "content": followup_prompt}

                context_blocks = []
                for m in st.session_state.messages:
                    if m["role"] == "assistant":
                        context_blocks.append({"role": "assistant", "content": m["content"]})
                    elif m["role"] == "user":
                        context_blocks.append({"role": "user", "content": m["content"]})

                resp = client.responses.create(
                    model="gpt-5.1",
                    input=[system_block] + context_blocks,
                    max_output_tokens=150  # keeps replies under ~120 words
                )
                reply = resp.output_text.strip()
               
                # force regeneration if blank or too short
                if not reply or len(reply.strip()) < 3:
                    resp = client.responses.create(
                        model="gpt-5.1",
                        input=[
                            {"role": "system", "content": "Your previous reply was empty. Please write a short, natural, human-like comment responding to the current chat context. Do NOT say sorry or mention the error."}
                        ] + [system_block] + context_blocks
                    )
                    reply = resp.output_text.strip()



                # NO-REPEAT NUDGE 
                recent_ai_texts = [m["content"] for m in st.session_state.messages if m["role"] == "assistant"][-10:]
                if reply in recent_ai_texts:
                    resp = client.responses.create(
                        model="gpt-5.1",
                        input=[{"role": "system", "content": "Avoid repeating yourself."}]
                            + [system_block] + context_blocks
                    )
                    reply = resp.output_text.strip()

                # cleanup
                reply = reply.replace("—", "...")
                reply = strip_name_prefix(reply, group_members)


                # hard length limit (rough realism: max 60 words)
                words = reply.split()
                if len(words) > 60:
                    reply = " ".join(words[:60]) + "..."

                # render + store
                timestamp = datetime.now().strftime("%H:%M:%S")
                display_time = datetime.now().strftime("%H:%M")
                message(
                    f"**{followup_speaker}:** {reply}\n\n<i style='color:gray; font-size: 0.8em'>{display_time}</i>",
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
                    "temp_round_marker": True  # used to group per round
                })

            st.rerun()


        # check for conversation end
        user_msg_count = sum(1 for m in st.session_state.messages if m["role"] == "user")

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