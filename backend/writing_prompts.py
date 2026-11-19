"""Original prompts modeled on IELTS Academic Writing task formats."""

from backend.reading_topics import TOPIC_GROUPS

WRITING_CATEGORY_THEMES = {
    **{category: tuple(label for label, _ in topics.values()) for category, topics in TOPIC_GROUPS.items()},
    "Arts and culture": ("museum attendance", "community arts programmes", "access to live performances"),
    "Business and the economy": ("small businesses", "consumer spending", "shopping habits"),
    "Cities and housing": ("housing affordability", "urban green spaces", "suburban development"),
    "Education and learning": ("adult education", "online courses", "school subject choices"),
    "Energy and resources": ("household energy use", "water conservation", "renewable electricity"),
    "Family and community": ("childcare arrangements", "volunteering", "care across generations"),
    "Food and agriculture": ("household food waste", "local food markets", "changing diets"),
    "Globalisation and trade": ("imports and exports", "international shopping", "local products in global markets"),
    "Government and public services": ("library access", "public spending", "digital public services"),
    "Law and public safety": ("road safety", "community safety", "emergency preparedness"),
    "Media and advertising": ("news consumption", "advertising to children", "social media use"),
    "Sport and recreation": ("participation in sport", "public leisure facilities", "outdoor activities"),
    "Tourism and heritage": ("visits to heritage sites", "seasonal tourism", "tourism in small communities"),
    "Transport and commuting": ("public transport use", "cycling to work", "commuting patterns"),
    "Work and employment": ("flexible working", "vocational training", "career changes"),
}

TASK_1_INSTRUCTIONS = (
    "Summarise the information by selecting and reporting the main features, and make "
    "comparisons where relevant. Write at least 150 words."
)
TASK_2_INSTRUCTIONS = (
    "Give reasons for your answer and include any relevant examples from your own "
    "knowledge or experience. Write at least 250 words."
)


def uses_process_visual(content):
    return any(task.get("process") for task in content.get("tasks", [content]))


WRITING_PROMPTS = {
    1: (
        {
            "topic": "bicycle-commuting",
            "title": "Commuting by bicycle",
            "prompt": "The table below shows the percentage of people who cycled to work in four cities "
                      f"in 2005, 2015, and 2025. {TASK_1_INSTRUCTIONS}",
            "table": [
                ["City", "2005", "2015", "2025"], ["Northford", "8%", "13%", "22%"],
                ["Elmbridge", "17%", "21%", "24%"], ["Westhaven", "11%", "9%", "14%"],
                ["Brookdale", "5%", "8%", "16%"],
            ],
        },
        {
            "topic": "household-electricity",
            "title": "Household electricity use",
            "prompt": "The bar chart below compares the proportion of household electricity used for "
                      f"five purposes in a country in 2000 and 2020. {TASK_1_INSTRUCTIONS}",
            "chart": {
                "title": "Share of household electricity use (%)",
                "years": ["2000", "2020"],
                "series": [
                    {"label": "Heating", "values": [39, 31]},
                    {"label": "Water heating", "values": [22, 19]},
                    {"label": "Kitchen appliances", "values": [18, 20]},
                    {"label": "Lighting", "values": [13, 7]},
                    {"label": "Other appliances", "values": [8, 23]},
                ],
            },
        },
        {
            "topic": "library-visits",
            "title": "Public library visits",
            "prompt": "The table below shows average monthly visits to four branches of a public library "
                      f"in three different years. {TASK_1_INSTRUCTIONS}",
            "table": [
                ["Branch", "2012", "2017", "2022"], ["Central", "8,600", "9,400", "8,100"],
                ["West", "3,800", "4,700", "6,200"], ["Riverside", "5,600", "5,100", "4,500"],
                ["University", "4,200", "5,900", "7,700"],
            ],
        },
        {
            "topic": "renewable-electricity",
            "title": "Sources of renewable electricity",
            "prompt": "The bar chart below shows the share of electricity generated from three renewable sources "
                      f"in a country in 2010, 2015 and 2020. {TASK_1_INSTRUCTIONS}",
            "chart": {
                "title": "Share of total electricity generation (%)",
                "years": ["2010", "2015", "2020"],
                "series": [
                    {"label": "Hydropower", "values": [18, 17, 16]},
                    {"label": "Wind", "values": [5, 9, 14]},
                    {"label": "Solar", "values": [1, 4, 10]},
                ],
            },
        },
        {
            "topic": "adult-education",
            "title": "Adult education enrolment",
            "prompt": "The table below shows enrolment in three evening courses at a college in 2012, 2017 "
                      f"and 2022. {TASK_1_INSTRUCTIONS}",
            "table": [
                ["Course", "2012", "2017", "2022"], ["Languages", "120", "138", "146"],
                ["Digital skills", "64", "110", "177"], ["Business", "152", "135", "122"],
            ],
        },
        {
            "topic": "household-water",
            "title": "Household water consumption",
            "prompt": "The table below shows the average amount of water used per household each day for "
                      f"four activities in two towns. {TASK_1_INSTRUCTIONS}",
            "table": [
                ["Activity", "Lockford (litres)", "Greenbank (litres)"], ["Bathing", "94", "78"],
                ["Laundry", "52", "61"], ["Cooking and cleaning", "48", "42"], ["Gardening", "31", "58"],
            ],
        },
    ),
    2: (
        {
            "topic": "flexible-working",
            "title": "Flexible working",
            "prompt": "Some people believe employers should let staff choose where they work. Others "
                      "believe staff should work together at a shared workplace. Discuss both views and "
                      f"give your own opinion. {TASK_2_INSTRUCTIONS}",
        },
        {
            "topic": "transport-investment",
            "title": "Transport investment",
            "prompt": "Governments should spend more money improving public transport than on building "
                      f"new roads. To what extent do you agree or disagree? {TASK_2_INSTRUCTIONS}",
        },
        {
            "topic": "online-learning",
            "title": "Online learning",
            "prompt": "A growing number of adults are choosing to study for qualifications online. "
                      f"Do the advantages of this development outweigh the disadvantages? {TASK_2_INSTRUCTIONS}",
        },
        {
            "topic": "food-waste",
            "title": "Food waste",
            "prompt": "In many countries, households throw away a large amount of food. Why does this "
                      f"happen? What could be done to reduce household food waste? {TASK_2_INSTRUCTIONS}",
        },
        {
            "topic": "public-green-space",
            "title": "Public green space",
            "prompt": "Some people believe that cities should turn unused public land into parks. Others "
                      "think the same land should be used for housing. Discuss both views and give your "
                      f"own opinion. {TASK_2_INSTRUCTIONS}",
        },
        {
            "topic": "digital-privacy",
            "title": "Digital privacy",
            "prompt": "Many online services collect information about their users to personalise what they "
                      "offer. Do the advantages of collecting this information outweigh the disadvantages? "
                      f"{TASK_2_INSTRUCTIONS}",
        },
        {
            "topic": "museum-access",
            "title": "Access to museums",
            "prompt": "Museums that receive public funding should offer free admission to everyone. "
                      f"To what extent do you agree or disagree? {TASK_2_INSTRUCTIONS}",
        },
        {
            "topic": "active-lifestyles",
            "title": "Physical activity in cities",
            "prompt": "People in some cities are becoming less physically active. Why is this happening, "
                      f"and what could local governments do to encourage more active lifestyles? {TASK_2_INSTRUCTIONS}",
        },
    ),
}
