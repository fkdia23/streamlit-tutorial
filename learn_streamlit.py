import streamlit as st

# Set page title and icon ( au niveau de onglet)
st.set_page_config(
    page_title="Hello World - Streamlit",
    page_icon="👋",
    layout="centered" # wide
)

#equivalent d'une balise h1 en html
st.title("Hello World! 👋")

# equivalent d'une balise h2 en html ( sous titre )
st.header("Welcome to Streamlit")

#equivalent sous titre h3
st.subheader("Let's build an app together!")

# equivalent d'une balise p en html
st.write("This is a simple Streamlit app that demonstrates how to use Streamlit to create")

# markdown text
st.markdown("""
    Streamlit is an open-source app framework for Machine Learning and Data Science teams.""")

#divider
st.divider()

# inquivalent d'un input text en html
name = st.text_input("Enter your name", "Type here...")

if name:
    st.write(f"Hello, {name}! Welcome to Streamlit.")
    st.success(f"Hello, {name}! Welcome to Streamlit.")
    st.snow()

st.info("une info")
st.warning("une warning")
st.error("une erreur")
st.success("une success")

age = st.slider("Select your age", 0, 100, 25)
st.write(f"You are {age} years old.")
st.text_input("Enter your email", "Type here...")


st.sidebar.header("🔧 Controls")
st.sidebar.write("You can add widgets here too.")
st.sidebar.button("Click me!")