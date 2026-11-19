"""Publisher options and original topic briefs used for Reading practice."""

from collections import Counter
from random import shuffle
from urllib.error import URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from backend.reading_topics import TOPIC_CATEGORIES, TOPICS

PUBLISHERS = {
    "the-conversation": ("The Conversation", "https://theconversation.com", "Science, society, and research"),
    "scientific-american": ("Scientific American", "https://www.scientificamerican.com", "Science, technology, and biology"),
    "bbc-future": ("BBC Future", "https://www.bbc.com/future", "Psychology, science, and the environment"),
    "smithsonian": ("Smithsonian Magazine", "https://www.smithsonianmag.com", "History, archaeology, and culture"),
    "nasa": ("NASA", "https://science.nasa.gov", "Space and science"),
    "our-world-in-data": ("Our World in Data", "https://ourworldindata.org", "Society, environment, and economics"),
    "nature": ("Nature", "https://www.nature.com/nature", "Research · advanced"),
    "project-gutenberg": ("Project Gutenberg", "https://www.gutenberg.org", "History, literature, and ideas"),
}

PUBLISHER_FEEDS = {
    "the-conversation": ("https://theconversation.com/us/articles.atom", "theconversation.com"),
    "scientific-american": ("https://www.scientificamerican.com/platform/syndication/rss/", "scientificamerican.com"),
    "smithsonian": ("https://www.smithsonianmag.com/rss/latest_articles/", "smithsonianmag.com"),
    "nasa": ("https://www.nasa.gov/feed/", "nasa.gov"),
    "our-world-in-data": ("https://ourworldindata.org/atom.xml", "ourworldindata.org"),
    "nature": ("https://www.nature.com/nature.rss", "nature.com"),
    "project-gutenberg": ("https://www.gutenberg.org/cache/epub/feeds/today.rss", "gutenberg.org"),
}

# These are original reference briefs. Publisher prose is not fetched or reproduced.
BRIEFS = {
    "the-conversation": (
        ("education", "How retrieval practice affects learning", "Contrast recalling material with rereading it, and discuss the value of spaced practice.", "/3-ways-to-study-better-according-to-cognitive-research-140230"),
        ("cities", "Measuring whether a neighbourhood is walkable", "Consider route continuity, the distribution of daily destinations, and barriers such as wide roads.", "/beyond-the-15-minute-city-what-really-makes-people-want-to-walk-287040"),
        ("climate-adaptation", "How communities prepare for extreme heat", "Compare shade, cooling centres, and warning systems, with attention to access.", "/urban-trees-cool-the-worlds-cities-more-than-we-thought-but-we-cant-rely-on-them-alone-281866"),
        ("work", "Why meetings expand in flexible workplaces", "Explore how coordination needs, shared records, and communication habits affect meeting time.", "/why-meetings-can-harm-employee-well-being-270899"),
        ("public-health", "What wastewater can tell a city", "Describe pooled sampling, its value for monitoring trends, and the limits of drawing individual conclusions.", "/wastewater-surveillance-reveals-pathogens-in-detroits-population-helping-monitor-and-predict-disease-outbreaks-since-2017-229171"),
        ("language", "How multilingual children use context", "Explain why language use can differ across home, school, and social settings.", "/do-you-speak-other-languages-at-home-this-will-not-hold-your-child-back-at-school-250405"),
    ),
    "scientific-american": (
        ("animal-behaviour", "How birds navigate over long distances", "Compare landmarks, celestial cues, and sensitivity to magnetic fields.", "/article/how-migrating-birds-use-quantum-effects-to-navigate/"),
        ("materials", "Why some materials recover their shape", "Describe temperature-dependent transitions and distinguish shape memory from ordinary elasticity.", "/article/shape-memory-alloys/"),
        ("sleep", "How light resets the circadian clock", "Describe timing, brightness, and the difference between circadian rhythms and sleep pressure.", "/article/q-a-why-is-blue-light-before-bedtime-bad-for-sleep/"),
        ("astronomy", "Discovering exoplanets with transit measurements", "Explain temporary dimming and the limitations of estimating a planet's properties from it.", "/article/how-it-works-planetary-double-take/"),
        ("plant-science", "Why plants close their stomata", "Explore the trade-off between absorbing carbon dioxide and losing water.", "/article/some-trees-hold-their-breath-during-wildfires/"),
        ("artificial-intelligence", "Why speech recognition struggles in noise", "Consider how two overlapping voices and changes in recording conditions affect recognition.", "/article/speech-getting-computers-understand-overlapping/"),
    ),
    "bbc-future": (
        ("climate-adaptation", "Designing cooler neighbourhoods", "Compare shading, reflective surfaces, and ventilation as ways to keep buildings cool.", "/future/article/20190822-are-there-alternatives-to-air-conditioning"),
        ("mental-health", "How environmental noise affects stress and sleep", "Discuss how traffic noise can disturb sleep and what makes exposure hard to measure.", "/future/article/20210315-why-noise-pollution-is-bad-for-your-heart"),
        ("sleep", "Why working at night disrupts sleep", "Discuss mismatches between light exposure, schedules, and circadian timing.", "/worklife/article/20171208-what-working-through-the-dead-of-night-does-to-your-body"),
        ("biodiversity", "Restoring wildlife corridors", "Explore how habitat links can support movement and how their success is measured.", "/future/article/20240521-these-wildlife-corridors-help-grizzly-bears"),
        ("transport", "Making short urban journeys easier without cars", "Compare walking, cycling, and access to nearby services.", "/worklife/article/20201214-how-15-minute-cities-will-change-the-way-we-socialise"),
        ("nutrition", "How preservation affects how long food lasts", "Compare storage conditions and preservation methods without making medical claims.", "/future/article/20200330-which-foods-are-best-to-eat-after-the-apocalypse"),
        ("water", "Capturing rainfall in busy cities", "Compare permeable surfaces, rain gardens, and storage during short, intense storms.", "/future/article/20220823-how-auckland-worlds-most-spongy-city-tackles-floods"),
    ),
    "smithsonian": (
        ("archaeology", "How archaeologists interpret broken pottery", "Explain what material, shape, and find location can reveal when complete objects are rare.", "/blogs/smithsonian-tropical-research-institute/2024/05/31/archeologists-learn-to-piece-together-the-past/"),
        ("art", "How historic pigments are identified", "Contrast visual inspection with material analysis, and discuss conservation limits.", "/smart-news/vibrant-colors-scream-are-fading-180974199/"),
        ("language", "How surviving letters document language change", "Compare private correspondence with formal records and discuss which voices survive.", "/smart-news/these-french-love-letters-were-just-opened-for-the-first-time-after-265-years-180983215/"),
        ("animal-behaviour", "What collections reveal about bird migration", "Discuss museum specimens, observation dates, and sampling biases.", "/science-nature/behind-scenes-birds-feather-studied-together-180947913/"),
        ("cities", "How old maps record changing neighbourhoods", "Compare map purposes and what street names, boundaries, and omissions can reveal.", "/history/interactive-map-compares-new-york-city-1836-today-180947939/"),
        ("plant-science", "Why museums preserve historical plant specimens", "Describe cataloguing and comparisons across sites and collection dates.", "/blogs/national-museum-of-natural-history/2021/05/06/why-plants-are-seeding-climate-studies/"),
    ),
    "nasa": (
        ("astronomy", "How planetary scientists study Europa", "Discuss indirect evidence for oceans and how flybys can test competing interpretations.", "/mission/europa-clipper/"),
        ("astronomy", "Why Mars samples matter", "Explain how rocks preserve evidence about earlier conditions and why context matters.", "/mission/mars-2020-perseverance/mars-rock-samples/"),
        ("astronomy", "How a space telescope observes exoplanets", "Distinguish transit measurements from atmospheric observations.", "/exoplanets/how-we-find-and-characterize/"),
        ("climate-adaptation", "Tracking sea level from space", "Describe satellite measurement and the difference between global trends and local experience.", "/earth/explore/earth-indicators/sea-leve/"),
        ("water", "Watching changes in water storage from orbit", "Explain how changes in Earth's gravity can reveal changes in stored water.", "/mission/grace-fo/"),
        ("geology", "Mapping Earth from orbit with Landsat", "Discuss why repeated images and consistent measurements are useful for observing land change.", "/mission/landsat/"),
        ("oceans", "What ocean colour reveals from space", "Explain how light reflected from the ocean can help track phytoplankton and why clouds limit observations.", "/mission/pace/"),
    ),
    "our-world-in-data": (
        ("public-health", "Comparing long-run life expectancy", "Distinguish population life expectancy at birth from a prediction for an individual.", "/life-expectancy"),
        ("renewable-energy", "Comparing renewable electricity across countries", "Distinguish absolute generation from a percentage of the electricity mix.", "/renewable-energy"),
        ("water", "Measuring access to safe drinking water", "Explore differences between physical infrastructure and reliable service.", "/water-access"),
        ("education", "Comparing years of schooling over time", "Distinguish enrolment, completion, and how much students learn.", "/global-education"),
        ("climate-adaptation", "Putting disaster losses in context", "Discuss exposure, vulnerability, and why reporting changes complicate historical comparisons.", "/natural-disasters"),
        ("biodiversity", "How land use affects biodiversity", "Balance agriculture, habitat conversion, and uncertainty in comparisons.", "/biodiversity"),
    ),
    "nature": (
        ("materials", "How researchers test self-healing polymers", "Contrast restoring appearance with recovering mechanical strength.", "/articles/s41467-021-20931-z"),
        ("genomics", "Why researchers compare genomes across populations", "Discuss sampling, population structure, and limits of causal inference.", "/articles/s41586-025-09290-7"),
        ("astronomy", "How researchers decide whether a biosignature is convincing", "Explain alternative explanations and why independent observations matter.", "/articles/d41586-025-01264-z"),
        ("climate-adaptation", "Distinguishing trends from variability in climate research", "Explain how baseline choice and observational coverage affect interpretation.", "/articles/ngeo2228"),
        ("mental-health", "Why replication matters in psychology", "Compare measurement reliability, study design, and independent replication.", "/articles/s41467-022-34748-x"),
        ("artificial-intelligence", "What benchmarks measure in scientific machine learning", "Explain training and test separation and the distinction between prediction and explanation.", "/articles/s42254-022-00441-7"),
        ("geology", "Using isotope ratios to reconstruct the past", "Discuss what chemical signals in geological samples reveal and why independent checks matter.", "/articles/s41467-024-48811-2"),
    ),
    "project-gutenberg": (
        ("work", "Division of labour in The Wealth of Nations", "Explain task specialisation and trade-offs in applying the argument to modern settings.", "/ebooks/3300"),
        ("animal-behaviour", "Observation and comparison in On the Origin of Species", "Discuss using examples to build an argument and how readers evaluate the evidence.", "/ebooks/1228"),
        ("plant-science", "How field observations shape Walden", "Explore what an individual observer can reveal about seasonal patterns and what remains uncertain.", "/ebooks/205"),
        ("education", "Education and civic life in The Republic", "Explore the link between schooling and models of citizenship, keeping historical context visible.", "/ebooks/1497"),
        ("art", "How readers reconstruct a setting in Pride and Prejudice", "Discuss how dialogue and social conventions build an understanding of a historical setting.", "/ebooks/1342"),
        ("science-history", "Technology and imagination in The Time Machine", "Consider how speculative fiction compares technological progress with social outcomes.", "/ebooks/35"),
    ),
}


def publisher_topic_ids(source):
    subjects = [brief[0] for brief in BRIEFS[source] if brief[0] in TOPIC_CATEGORIES]
    counts = Counter(TOPIC_CATEGORIES[subject] for subject in subjects)
    return list(dict.fromkeys(subject for subject in subjects if counts[TOPIC_CATEGORIES[subject]] >= 3))


def reference_url_key(url):
    parts = urlsplit(url)
    return parts._replace(path=parts.path.rstrip("/"), query="", fragment="").geturl()


def publisher_headlines(source, topic, used_references):
    if source not in PUBLISHER_FEEDS:
        return []
    feed, allowed_host = PUBLISHER_FEEDS[source]
    request = Request(feed, headers={"User-Agent": "IELTSAcademicPractice/1.0"})
    try:
        with urlopen(request, timeout=8) as response:
            root = ElementTree.fromstring(response.read(1_000_000))
    except (URLError, OSError, ElementTree.ParseError):
        return []
    name = PUBLISHERS[source][0]
    homepage = reference_url_key(PUBLISHERS[source][1])
    keywords = set(TOPICS[topic][1].split()) - {"science", "technology", "research", "public"} if topic else set()
    seen = set(used_references)
    references = []
    for item in root.findall(".//{*}item") + root.findall(".//{*}entry"):
        title = " ".join((item.findtext("{*}title") or "").split())
        link = next((link for link in item.findall("{*}link")
                     if link.get("rel", "alternate") == "alternate"), None)
        raw_url = (link.get("href") or link.text or "").strip() if link is not None else ""
        try:
            parts = urlsplit(raw_url)
        except ValueError:
            continue
        host = parts.hostname or ""
        if parts.scheme != "https" or (host != allowed_host and not host.endswith(f".{allowed_host}")):
            continue
        key = reference_url_key(raw_url)
        if (not parts.path.strip("/") or key == homepage or key in seen or not title
                or (keywords and not any(word in title.casefold() for word in keywords))):
            continue
        seen.add(key)
        references.append({"reference_id": key, "provider": name, "title": title, "url": raw_url,
                           "attribution": name, "kind": "headline"})
    shuffle(references)
    return references


def publisher_sources(source, topic, used_references):
    name, homepage, _ = PUBLISHERS[source]
    candidates = []
    for index, (subject, title, extract, path) in enumerate(BRIEFS[source], 1):
        reference_id = f"{source}:{index}"
        url = urljoin(homepage, path)
        if reference_id in used_references or reference_url_key(url) in used_references:
            continue
        candidates.append((subject, {
            "reference_id": reference_id, "provider": name, "title": title,
            "url": url, "attribution": name,
            "kind": "reference_brief", "extract": extract,
        }))
    shuffle(candidates)
    if topic:
        category = TOPIC_CATEGORIES[topic]
        candidates = [item for item in candidates if TOPIC_CATEGORIES.get(item[0]) == category]
        candidates.sort(key=lambda item: item[0] != topic)
    headlines = publisher_headlines(source, topic, used_references)
    headline_keys = {reference_url_key(item["url"]) for item in headlines}
    return (headlines + [material for _, material in candidates
                         if reference_url_key(material["url"]) not in headline_keys])[:3]
