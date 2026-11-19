-- Fails when the model's rows differ in number from the items its sources list: the
-- reconciliation of a model with the bronze it reads, where each source row lists
-- its items in the list `items` (d008, Transformation in dbt).
{% test count_matches_listed_items(model, sources, items) %}

    with

    listed as (

        {% for listing in sources %}
            -- A row with no list counts no item, as does a source with no rows.
            select coalesce(sum(len({{ items }})), 0) as item_count
            from {{ listing }}
            {% if not loop.last %}union all{% endif %}
        {% endfor %}

    ),

    compared as (

        select
            (select sum(listed.item_count) from listed) as listed_items,
            (select count(*) from {{ model }}) as model_rows

    )

    select
        compared.listed_items,
        compared.model_rows
    from compared
    where compared.listed_items != compared.model_rows

{% endtest %}
