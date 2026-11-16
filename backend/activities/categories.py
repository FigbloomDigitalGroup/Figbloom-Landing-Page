"""The activity categories, defined once.

The model's choices, the public filter chips, the admin form's <select> and the
card colours/icons all read from this list, so adding a category later means
adding one entry here (plus a CSS colour in activities.css) and running
makemigrations — nothing else has to be kept in step by hand.
"""

# key        stored in the database and used in ?category=<key>
# label      singular — the pill on a card ("Workshop")
# plural     the filter chip ("Workshops")
# tab        whether the public Activities page offers a filter tab for it.
#            A category without a tab can still be chosen in the dashboard; its
#            entries show up under "All Activities" with their category label.
# icon       a Lucide icon name, rendered by lucide.min.js
CATEGORIES = [
    {'key': 'event', 'label': 'Event', 'plural': 'Events', 'icon': 'calendar-days', 'tab': True},
    {'key': 'update', 'label': 'Update', 'plural': 'Updates', 'icon': 'newspaper', 'tab': True},
    {'key': 'community', 'label': 'Community', 'plural': 'Community', 'icon': 'heart-handshake', 'tab': True},
    {'key': 'achievement', 'label': 'Achievement', 'plural': 'Achievements', 'icon': 'trophy', 'tab': True},
    {'key': 'workshop', 'label': 'Workshop', 'plural': 'Workshops', 'icon': 'presentation', 'tab': False},
]

CATEGORY_CHOICES = [(c['key'], c['label']) for c in CATEGORIES]
CATEGORY_BY_KEY = {c['key']: c for c in CATEGORIES}
