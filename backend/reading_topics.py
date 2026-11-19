"""Topic choices and source search terms for Academic Reading."""

TOPIC_GROUPS = {
    "Environment": {
        "climate-adaptation": ("Climate adaptation", "climate adaptation resilience"),
        "biodiversity": ("Biodiversity and conservation", "biodiversity conservation ecology"),
        "oceans": ("Oceans and marine ecosystems", "marine ecosystem ocean ecology"),
        "renewable-energy": ("Renewable energy", "renewable energy technology"),
        "water": ("Water resources", "water resource management freshwater"),
    },
    "Science": {
        "astronomy": ("Astronomy and space", "astronomy space exploration"),
        "geology": ("Geology and natural hazards", "geology geological hazard earth"),
        "animal-behaviour": ("Animal behaviour", "animal behaviour ethology"),
        "plant-science": ("Plant science", "plant science botany ecology"),
        "materials": ("Materials science", "materials science innovative materials"),
    },
    "Health": {
        "public-health": ("Public health", "public health prevention epidemiology"),
        "nutrition": ("Nutrition and diet", "human nutrition diet science"),
        "sleep": ("Sleep and circadian rhythms", "sleep circadian rhythm science"),
        "exercise": ("Exercise and movement", "exercise physiology physical activity"),
        "mental-health": ("Psychology and mental health", "mental health psychology wellbeing"),
    },
    "Technology": {
        "artificial-intelligence": ("Artificial intelligence", "artificial intelligence applications"),
        "robotics": ("Robotics and automation", "robotics automation engineering"),
        "transport": ("Transportation and mobility", "transportation mobility public transport"),
        "communication": ("Communication technology", "communication technology telecommunications"),
        "manufacturing": ("Manufacturing and innovation", "manufacturing innovation industrial technology"),
    },
    "Society and culture": {
        "education": ("Education and learning", "education learning science"),
        "cities": ("Cities and urban design", "urban design city planning"),
        "archaeology": ("Archaeology and ancient societies", "archaeology ancient civilization"),
        "language": ("Language and linguistics", "language linguistics language change"),
        "art": ("Art, design, and architecture", "art architecture design history"),
        "work": ("Work and organisations", "work organization workplace sociology"),
    },
}

TOPICS = {key: topic for group in TOPIC_GROUPS.values() for key, topic in group.items()}
TOPIC_CATEGORIES = {key: name for name, group in TOPIC_GROUPS.items() for key in group}
MIXED_TOPICS = "Mixed topics"

WIKIPEDIA_CATEGORIES = {
    "climate-adaptation": "Climate change adaptation", "biodiversity": "Biodiversity",
    "oceans": "Marine ecology", "renewable-energy": "Renewable energy", "water": "Water resources",
    "astronomy": "Astronomy", "geology": "Geology", "animal-behaviour": "Ethology",
    "plant-science": "Botany", "materials": "Materials science", "public-health": "Public health",
    "nutrition": "Nutrition", "sleep": "Sleep", "exercise": "Physical exercise",
    "mental-health": "Mental health", "artificial-intelligence": "Artificial intelligence",
    "robotics": "Robotics", "transport": "Transport", "communication": "Telecommunications",
    "manufacturing": "Manufacturing", "education": "Education", "cities": "Urban planning",
    "archaeology": "Archaeology", "language": "Linguistics", "art": "Architecture",
    "work": "Organizational behavior",
}
