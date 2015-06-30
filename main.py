import requests
import json

from flask import Flask
from flask import request, render_template

app = Flask(__name__)

@app.route('/add_task')
def add_task():
    print 'add_task'
    if request.method == 'GET':
        spider = request.args.get('spider', 'amazon')
        search_term = request.args.get('searchterms_str', '')
        page = request.args.get('page', '')

        url = 'http://52.8.237.119/schedule.json'

        if not search_term:
            return "You should provide search term"

        params = {'project': 'spiders',
                  'spider': spider,
                  'searchterms_str': search_term}
        if page:
            params['page'] = page

        res = requests.post(url, params=params)

        if res.status_code == 200:
            data = json.loads(res.content)
            if data['status'] == 'ok':
                task_id = data['jobid']

                link = 'http://52.8.237.119/items/spiders/' + spider + '/' \
                       + task_id + '.jl'
                return render_template('main.html', link=link)
            else:
                return data['message']
        else:
            return res.content

if __name__ == "__main__":
    app.debug = True
    app.run()

