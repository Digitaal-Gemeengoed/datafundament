{#
  Materialisatie voor Iceberg: de tabel één keer maken, daarna elke run legen en
  opnieuw vullen, in één transactie. Zo blijft de tabel bestaan voor lezers
  (Trino), en houdt Iceberg per run een snapshot: time travel op de uniforme laag.
  Bij een nieuwe of andere kolom: dbt build --full-refresh (dan wordt de tabel opnieuw gemaakt).

  De standaard materialisatie van dbt-duckdb (tijdelijke tabel, hernoemen,
  verwijderen) is op Iceberg niet getest; deze is eenvoudiger en uitlegbaar.
#}
{% materialization iceberg_tabel, adapter='duckdb' %}
  {%- set doel = this.incorporate(type='table') -%}
  {%- set bestaand = adapter.get_relation(database=doel.database, schema=doel.schema, identifier=doel.identifier) -%}

  {{ run_hooks(pre_hooks) }}
  {% do adapter.create_schema(doel) %}

  {% if bestaand is not none and should_full_refresh() %}
    {% call statement('weg') -%} DROP TABLE {{ doel }} {%- endcall %}
    {% set bestaand = none %}
  {% endif %}

  {% if bestaand is none %}
    {% call statement('main') -%}
      CREATE TABLE {{ doel }} AS SELECT * FROM ({{ sql }}) AS bron
    {%- endcall %}
  {% else %}
    {% call statement('main') -%}
      DELETE FROM {{ doel }};
      INSERT INTO {{ doel }} BY NAME SELECT * FROM ({{ sql }}) AS bron
    {%- endcall %}
  {% endif %}

  {{ run_hooks(post_hooks) }}
  {% do adapter.commit() %}
  {{ return({'relations': [doel]}) }}
{% endmaterialization %}
