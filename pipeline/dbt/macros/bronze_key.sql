-- The system and capture instant of a bronze object, as a struct, from its local
-- path, which ends with its bronze key (ADR-0012, Collectors decoupled by output
-- contract): every model that reads bronze takes them from here, so that the key
-- is parsed in one place, as contracts/bronze-keys.json sets it.
{% macro bronze_key(filename) %}
    {#- A block set keeps the pattern's backslashes as written. -#}
    {%- set pattern -%}
        raw/([a-z]+)/[a-z_]+/[0-9-]+/(\d{8}T\d{6}Z)\.json\.gz$
    {%- endset -%}
    {
        'system': regexp_extract({{ filename }}, '{{ pattern }}', 1),
        'captured_at': timezone(
            'UTC',
            strptime(
                regexp_extract({{ filename }}, '{{ pattern }}', 2),
                '%Y%m%dT%H%M%SZ'
            )
        )
    }
{% endmacro %}
