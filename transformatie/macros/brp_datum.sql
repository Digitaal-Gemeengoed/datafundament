{# Een datum uit de BRP (JJJJMMDD, met 00 voor onbekend) als DATE; onvolledig wordt NULL. #}
{% macro brp_datum(kolom) -%}
  try_strptime(nullif(nullif({{ kolom }}, ''), '00000000'), '%Y%m%d')::date
{%- endmacro %}
