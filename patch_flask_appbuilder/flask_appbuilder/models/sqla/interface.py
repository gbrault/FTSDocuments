from sqlalchemy.orm.query import Query
from flask_appbuilder.utils.base import (
    get_column_leaf,
    get_column_root_relation,
    is_column_dotted,
)
from sqlalchemy.orm.util import AliasedClass
from typing import Any, Dict, List, Optional, Tuple, Type, Union
from sqlalchemy import asc, desc
import flask_appbuilder.models.sqla.original_interface as patch_interface
import sys
from flask_appbuilder.models.filters import Filters
from flask_appbuilder.models.sqla import filters, Model
from flask_appbuilder.exceptions import InterfaceQueryWithoutSession

def apply_order_by(
    self,
    query: Query,
    order_column: Any,
    order_direction: str,
    aliases_mapping: Dict[str, AliasedClass] = None,
) -> Query:
    """Applies order by to a query
    
    allows ordering by multiple columns
    """
    if isinstance(order_column, str):
        if order_column != "":
            # if Model has custom decorator **renders('<COL_NAME>')**
            # this decorator will add a property to the method named *_col_name*
            if hasattr(self.obj, order_column):
                if hasattr(getattr(self.obj, order_column), "_col_name"):
                    order_column = getattr(self._get_attr(order_column), "_col_name")
            _order_column = self._get_attr(order_column) or order_column

            if is_column_dotted(order_column):
                root_relation = get_column_root_relation(order_column)
                # On MVC we still allow for joins to happen here
                if not self.is_model_already_joined(
                    query, self.get_related_model(root_relation)
                ):
                    query = self._query_join_relation(
                        query, root_relation, aliases_mapping=aliases_mapping
                    )
                column_leaf = get_column_leaf(order_column)
                _alias = self.get_alias_mapping(root_relation, aliases_mapping)
                _order_column = getattr(_alias, column_leaf)
            if order_direction == "asc":
                query = query.order_by(asc(_order_column))
            else:
                query = query.order_by(desc(_order_column))
        return query
    elif isinstance(order_column, tuple):
        for col in order_column:
            query = self.apply_order_by(query, col, order_direction)
        return query
    else:
        return query

def query(
    self,
    filters: Optional[Filters] = None,
    order_column: str = "",
    order_direction: str = "",
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    select_columns: Optional[List[str]] = None,
    outer_default_load: bool = False,
) -> Tuple[int, List[Model]]:
    """
    Returns the results for a model query, applies filters, sorting and pagination
    :param filters: A Filter class that contains all filters to apply
    :param order_column: name of the column to order
    :param order_direction: the direction to order <'asc'|'desc'>
    :param page: the current page
    :param page_size: the current page size
    :param select_columns: A List of columns to be specifically selected
    on the query. Supports dotted notation.
    :param outer_default_load: If True, the default load for outer joins will be
        applied. This is useful for when you want to control
        the load of the many-to-many relationships at the model level.
        we will apply:
            https://docs.sqlalchemy.org/en/14/orm/loading_relationships.html#sqlalchemy.orm.Load.defaultload
    :return: A tuple with the query count (non paginated) and the results
    """
    if not self.session:
        raise InterfaceQueryWithoutSession()
    query = self.session.query(self.obj)

    count = self.query_count(query, filters, select_columns)
    query = self.apply_all(
        query,
        filters,
        order_column,
        order_direction,
        page,
        page_size,
        select_columns,
    )
    query_results = query.all()

    # add filters to the result for further processing (render can highlight text for example)
    for i,item in enumerate(query_results):
        query_results[i]._filters = filters

    result = []
    for item in query_results:
        if hasattr(item, self.obj.__name__):
            result.append(getattr(item, self.obj.__name__))
        else:
            return count, query_results
    return count, result
    

patch_interface.SQLAInterface.apply_order_by = apply_order_by
patch_interface.SQLAInterface.query = query
sys.modules[__name__].__dict__.update(patch_interface.__dict__) 