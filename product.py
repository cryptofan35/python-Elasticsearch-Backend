import os
import mysql.connector
from elasticsearch7 import Elasticsearch, helpers
from dotenv import load_dotenv
import time

from alias import add_alias

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

DB_HOST = os.environ.get("DB_HOST")
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DATABASE = os.environ.get("DB_DATABASE")

limit_count = None
new_index = "primary_products"
old_index = "secondary_products"


def query():
    initial_db = None
    initial_cursor = None

    try:
        initial_db = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DATABASE
        )

        initial_cursor = initial_db.cursor(prepared=True)

        sql_query = """
            SELECT
                pm.id AS productID, pm.PNAME AS productName, pm.PURL AS productUrl, pr.pfad AS img,
                pm.TESTS AS tests, pm.SCORE AS score, pa.punkte AS points, CONCAT(k.kategorieName, ", ",
                h.herstellerName) AS keyword
            FROM
                pname2pid_mapping  pm
            INNER JOIN
                produktbilder pr ON (pm.id = pr.produktID)
            INNER JOIN
                pname2pid_angebote pa ON (pa.produktID = pm.id)
            INNER JOIN
                kategorien k ON (k.id = pm.kategorieID)
            INNER JOIN
                hersteller h ON(h.id = pm.herstellerID)
            WHERE
                pr.pos = 1 AND
                pr.groesse = 'S'
        """

        # sql_query = """
        #     SELECT
        #         pa.produktID AS productID, pm.PNAME AS productName, pm.PURL AS productUrl, pr.pfad AS img,
        #         pm.TESTS AS tests, pm.SCORE AS score, pa.punkte AS points
        #     FROM
        #         pname2pid_angebote pa
        #     LEFT JOIN
        #         produktbilder pr ON (pa.produktID = pr.produktID)
        #     LEFT JOIN
        #         pname2pid_mapping pm ON (pa.produktID = pm.id)
        #     WHERE
        #         pr.pos = 1 AND
        #         pr.groesse = 'S'
        # """

        # sql_query = """
        #     SELECT
        #         p.id productID, p.PNAME productName, p.PURL AS productUrl, pb.pfad AS img, p.TESTS AS tests,
        #         p.SCORE AS score, pa.punkte AS points
        #     FROM
        #         pname2pid_mapping p
        #     LEFT JOIN
        #         pname2pid_angebote pa ON (pa.produktID = p.id)
        #     LEFT JOIN
        #         produktbilder pb ON(pb.produktID = p.ID AND pb.groesse = 'O' AND pb.pos = 1)
        #     LEFT JOIN
        #         shops_offers s ON (s.produktID = p.id)
        #     LEFT JOIN
        #         hersteller h ON(h.id = p.herstellerID)
        #     WHERE
        #         p.gesperrt = 0 AND h.gesperrt = 0
        #     GROUP BY
        #         p.id
        #     ORDER BY
        #         p.noindex DESC,
        #         pa.punkte DESC,
        #         pa.sortPos ASC,
        #         p.SCORE DESC,
        #         p.TESTS DESC,
        #         COUNT(DISTINCT s.angebotsID) DESC,
        #         p.TESTSIEGER DESC,
        #         COUNT(pb.id) DESC
        # """

        if limit_count is not None:
            sql_query += " LIMIT %s"
            initial_cursor.execute(sql_query, (limit_count,))
        else:
            initial_cursor.execute(sql_query)

        return initial_cursor.fetchall()

    except mysql.connector.Error as e:
        print("Failed to query table in MySQL: {}".format(e))
        return []

    finally:
        if initial_db and initial_db.is_connected():
            initial_cursor.close()
            initial_db.close()


def connect_elasticsearch():
    _es = None
    _es = Elasticsearch(['search.testbericht.de'], scheme="https", port=443, timeout=5000.0, bulk_size=10000)
    if _es.ping():
        print('Connect to Elasticsearch')
    else:
        print('it could not connect!')
    return _es


def create_index(es_object, index_name):
    created = False

    settings = {
        "settings": {
            "number_of_shards": 4,
            "number_of_replicas": 1
        },
        "mappings": {
            "properties": {
                "dynamic": "strict",
                "id": {
                    "type": "long",
                },
                "name": {
                    "type": "text",
                    "fielddata": {
                        "loading": "eager"
                    }
                },
                "url": {
                    "type": "text",
                },
                "img": {
                    "type": "text",
                },
                "test": {
                    "type": "long",
                },
                "score": {
                    "type": "long",
                },
                "points": {
                    "type": "long",
                },
                "keyword": {
                    "type": "text",
                    "fielddata": {
                        "loading": "eager"
                    }
                }
            }
        }
    }

    try:
        if not es_object.indices.exists(index_name):
            es_object.indices.create(index=index_name, ignore=400, body=settings)
        created = True
    except Exception as ex:
        print(str(ex))
    finally:
        return created


def get_index_name(es_object, index_name):
    exist = True

    try:
        if not es_object.indices.exists(index_name):
            exist = False
    except Exception as ex:
        print(str(ex))
    finally:
        return exist


def main():
    print("=========== Start Products ===========")

    start_time = time.time()

    es_object = connect_elasticsearch()

    if get_index_name(es_object=es_object, index_name=new_index):
        ind_name = old_index
        remove_name = new_index
    else:
        ind_name = new_index
        remove_name = old_index
    create_index(es_object=es_object, index_name=ind_name)

    records = query()
    query_time = time.time()
    delta_query = query_time - start_time
    print("--- Query: {:10.1f} seconds ---".format(delta_query))

    products = []
    for record in records:
        row = {
            "id": int(record[0]),
            "name": record[1].decode() if record[1] else "",
            "url": record[2].decode() if record[2] else "",
            "img": record[3].decode() if record[3] else "",
            "test": int(record[4]) if record[4] else 0,
            "score": int(record[5]) if record[5] else 0,
            "points": int(record[6]) if record[6] else 0,
            "keyword": record[7].decode() if record[7] else ""
        }

        products.append(row)

    json_time = time.time()
    delta_json = json_time - query_time
    print("--- Json: {:10.1f} seconds ---".format(delta_json))

    helpers.bulk(es_object, products, index=ind_name)
    elastic_time = time.time()
    delta_elastic = elastic_time - json_time
    print("--- Elastic: {:10.1f} seconds ---".format(delta_elastic))
    print("--- Total: {:10.1f} seconds ---".format(delta_query + delta_json + delta_elastic))
    print("Imported Records:", len(products))

    add_alias(option='products', add_index=ind_name)
    if get_index_name(es_object, remove_name):
        es_object.indices.delete(index=remove_name, ignore=[400, 404])
    alias_time = time.time()
    delta_alias = alias_time - elastic_time
    print("--- Alias: {:10.1f} seconds ---".format(delta_alias))

    print("============ End Products ===========")


if __name__ == '__main__':
    main()
