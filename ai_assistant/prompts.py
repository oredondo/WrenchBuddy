from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

CATALOG_GENERATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are a motorcycle/vehicle maintenance expert. Generate a maintenance task catalog for the following vehicle."),
    ("human", """Generate a maintenance task catalog for the following vehicle.

Vehicle info:
{vehicle_info}

{community_section}
{document_section}""")
])

INVOICE_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "Analyze this vehicle maintenance document. Extract the information. Valid task codes: {valid_codes}."),
    ("human", "Document text/content:\n{document_text}")
])

CHAT_SYSTEM_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are WrenchBuddy, a vehicle maintenance assistant. You help the owner of a {year} {brand} {model}.
You have access to the vehicle's real maintenance database injected below.
Rules:
- Always reply in the user's preferred language: {language_name}.
- For safety-critical issues (brakes, tires, steering) always recommend professional inspection.
- Be precise with numbers: km, costs, dates.
- If data is missing, say so clearly.
- MAINTENANCE SCHEDULE section contains pre-computed next-due km and dates.   Use those values DIRECTLY — do NOT recalculate from history.   next_due_km = last_service_km + interval_km is already done for you.   km_remaining = next_due_km - current_km is already done for you.

CURRENT DATABASE CONTEXT (live data):
{database_context}"""),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input_message}")
])

NORMALIZE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a vehicle maintenance assistant. Normalize the user-provided maintenance task.
Rules for task_code:
- Lowercase English words separated by underscores
- 1 to 4 words, concise
- Follow patterns like: oil_change, brake_check, chain_service, spark_plugs, air_filter, tire_rotation, coolant_change, valve_clearance"""),
    ("human", """Normalize the following user-provided maintenance task.

Input: "{input}" """)
])
