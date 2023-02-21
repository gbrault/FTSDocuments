import sys
import flask_appbuilder.models.sqla.original_filters as patch_filters
from flask_babel import lazy_gettext
from flask_appbuilder.models.filters import (
    BaseFilter,
)
import sqlalchemy

class FilterMatch(BaseFilter):
    name = lazy_gettext("Match")
    arg_name = "mt"
    hook = None

    def apply(self, query, value):
        query, field = patch_filters.get_field_setup_query(query, self.model, self.column_name)
        if self.hook is not None:
            return self.hook(query, field, value)
        return query.filter(sqlalchemy.func.match(value,field))

patch_filters.FilterMatch = FilterMatch
# update the conversion table
new_filters = []
for filter in patch_filters.SQLAFilterConverter.conversion_table:
    if filter[0] in ["is_text","is_string"]:
        filter[1].insert(0,FilterMatch) # addit on top
    new_filters.append(filter)
patch_filters.SQLAFilterConverter.conversion_table = tuple(new_filters)
sys.modules[__name__].__dict__.update(patch_filters.__dict__)