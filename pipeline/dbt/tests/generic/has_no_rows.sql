-- Fails on each row of the model: the check of an audit model whose rows are the
-- findings, such as the fields of a schema drift; with dbt's `where` config, on
-- each row that matches it, such as a capture whose status is a drop (d008,
-- Transformation in dbt).
{% test has_no_rows(model) %}

    select * from {{ model }}

{% endtest %}
