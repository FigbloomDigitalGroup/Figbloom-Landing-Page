"""The activity categories, defined once.

The model's choices, the public filter chips, the admin form's <select> and the
card colours/icons all read from this list, so adding a category later means
adding one entry here (plus a CSS colour in activities.css) and running
makemigrations — nothing else has to be kept in step by hand.
"""

# key        stored in the database and used in ?category=<key>
# label      singular — the pill on a card ("Workshop")
# plural     the filter chip ("Workshops")
# icon       a Lucide icon name, rendered by lucide.min.js
CATEGORIES = [
    {'key': 'event', 'label': 'Event', 'plural': 'Events', 'icon': 'calendar-days'},
    {'key': 'update', 'label': 'Update', 'plural': 'Updates', 'icon': 'newspaper'},
    {'key': 'community', 'label': 'Community', 'plural': 'Community', 'icon': 'heart-handshake'},
    {'key': 'achievement', 'label': 'Achievement', 'plural': 'Achievements', 'icon': 'trophy'},
    {'key': 'workshop', 'label': 'Workshop', 'plural': 'Workshops', 'icon': 'presentation'},
    {'key': 'team', 'label': 'Team Activity', 'plural': 'Team Activities', 'icon': 'users-round'},
]

CATEGORY_CHOICES = [(c['key'], c['label']) for c in CATEGORIES]
CATEGORY_BY_KEY = {c['key']: c for c in CATEGORIES}
