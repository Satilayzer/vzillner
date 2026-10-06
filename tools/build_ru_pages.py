"""Generates the Russian pages (ru/...) from the German Framer export and syncs CMS text
into the server-rendered HTML.

Framer renders the Russian locale on the client when a page's hydration data carries the
ru-RU locale id, but the export only contains the German HTML. For every German page this
script writes ru/<same path>.html with:
  * the ru-RU locale id, lang attribute, canonical/og:url and internal links under /ru/;
  * CMS values (title, description, list) and the embedded handover data taken from the
    Russian CMS chunk, so hydration starts from Russian data;
  * remaining static texts translated via tools/ru_ssr_dict.json (German -> Russian text
    pairs collected from the rendered pages), so visitors don't see German before hydration.

German CMS pages get the same CMS sync from the German chunk (used for the corrected
"Moderne Therapieansätze" page).

Run from the repo root after apply_ru_texts.py and apply_cms_texts.py:
    python tools/build_ru_pages.py
"""
import html
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from framercms import read_chunk  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
FRAMER = ROOT / 'framer'
DICT = ROOT / 'tools' / 'ru_ssr_dict.json'
SITE = 'https://vzillner.com'
COLLECTION = 'd4b56bf5-f569-45f0-8993-8bbe393bfc46'
RU = 'TgnGYZiP3'
PAGES = ['index.html', 'behandlung.html', 'zur-person.html', 'villa.html', 'kontakt.html', 'formular.html',
         'datenschutzerklaerung.html', 'datenschutzhinweis.html']
TITLE, SLUG, DESCRIPTION, SUBHEADING, CONTENT = 'gnFtgisK4', 'o_MlKaKt_', 'dOCOCZd6E', 'A7N2vDMyq', 'AKQmf1Ygp'
PRESET = 'framer-styles-preset-simcg6'

DESCRIPTION_RU = {
    'Die Ordination V. Zillner steht für moderne Medizin, persönliche Betreuung und eine ruhige, vertrauensvolle Atmosphäre.':
        'Медицинская практика В. Циллнер — это современная медицина, индивидуальный подход и спокойная, доверительная атмосфера.',
}

# Texts the DOM-diff collection couldn't pair: the villa slider on the home page (carousel
# position differs between renders) and headings Framer splits into one <span> per word.
MANUAL_PAIRS = {
    'Historisches Erbe Wiens': 'Историческое наследие Вены',
    'Die Villa an dieser Adresse ist eng mit der Geschichte der Villa Gutmann verbunden. Als Teil des Wiener Cottageviertels steht sie für architektonische Qualität, kulturelles Erbe und den besonderen Geist ihrer Zeit.':
        'Вилла по этому адресу тесно связана с историей виллы Гутманн. Являясь частью венского коттеджного квартала, она отражает высокое качество архитектуры, культурное наследие и особую атмосферу своей эпохи.',
    'Architektur mit Geschichte': 'Архитектура с историей',
    'Errichtet im späten 19. Jahrhundert im neugotischen Stil, erzählt die Villa von einer bedeutenden Epoche Wiens. Ihre Geschichte verbindet architektonische Eleganz mit gesellschaftlichem und kulturellem Anspruch.':
        'Построенная в конце XIX века в неоготическом стиле, вилла рассказывает об одной из значимых эпох Вены. Её история объединяет архитектурную элегантность с высоким общественным и культурным статусом.',
    'Ein Haus mit Seele': 'Дом с душой',
    'Die ehemalige Villa Gutmann war nicht nur ein repräsentatives Wohnhaus, sondern auch Ausdruck einer ganzen Familiengeschichte. Bis heute bewahrt das Gebäude die Atmosphäre vergangener Zeiten und seinen besonderen Charakter.':
        'Бывшая вилла Гутманн была не просто представительским жилым домом, а частью целой семейной истории. До наших дней здание сохранило атмосферу ушедших эпох и свой особенный характер.',
    'Zeichen einer Epoche': 'Знамение эпохи',
    'Die Villa spiegelt den Reichtum und das Selbstverständnis einer einflussreichen Wiener Unternehmerfamilie wider. Gleichzeitig erzählt sie von Wandel, Verlust und der sorgfältigen Bewahrung historischer Substanz.':
        'Вилла отражает богатство и самосознание влиятельной венской семьи предпринимателей. В то же время она повествует о переменах, утрате и бережном сохранении исторического наследия.',
    # zur-person: milestones table
    'Studium Humanmedizin Wien': 'Обучение по специальности «Лечебное дело» в Вене',
    'Facharztdiplom Anästhesie erhalten': 'Получение диплома врача-специалиста по анестезиологии',
    'Beginn freiberufliche Tätigkeit': 'Начало самостоятельной профессиональной деятельности',
    'Ärztin für Allgemeinmedizin': 'Получение квалификации врача общей практики',
    'Eigene Ordination Wien gegründet': 'Открытие собственной медицинской практики в Вене',
    # mobile menu button and kontakt address (only rendered at other breakpoints / changed later)
    'Menu': 'Меню',
    '1180 Wien': '1180 Вена',
    # formular
    'Absenden': 'Отправить',
    'Ihr Name': 'Ваше имя',
    'Ihre Telefonnummer': 'Ваш номер телефона',
    'Ihre E-Mail-Adresse': 'Ваш адрес электронной почты',
    'Ihr Anliegen oder kurze Beschreibung Ihres Anliegens': 'Ваш запрос или краткое описание вашего запроса',
}
# Same German text, different Russian per page.
PAGE_PAIRS = {
    'datenschutzerklaerung.html': {
        'Dr. Valeria Zillner': 'Д-р Валерия Циллнер',
        'Datum und Uhrzeit des Zugriffs': 'Дату и время доступа',
    },
    'datenschutzhinweis.html': {
        'Datum und Uhrzeit des Zugriffs': 'дата и время доступа',
    },
}
# German <p> whose Russian version has a different structure: list of paragraphs, each a
# list of lines separated by <br>.
STRUCT_PAIRS = {
    'Die Villa Zillner ist ein Ort, an dem medizinische Kompetenz, Ruhe und ein stilvolles Ambiente zusammenkommen. Sie steht für eine persönliche Betreuung in einer besonderen Umgebung, die Vertrauen, Diskretion und Wohlbefinden vermittelt. Mit ihrer eleganten Architektur und ihrer ruhigen Ausstrahlung bildet die Villa den idealen Rahmen für eine moderne Ordination. Hier verbindet sich fachärztliche Betreuung mit einer Atmosphäre, in der sich Patientinnen und Patienten gut aufgehoben fühlen können. Die Villa Zillner ist nicht nur ein Standort, sondern ein Teil der Philosophie von Dr. Valeria Zillner: Medizin auf hohem Niveau, verbunden mit persönlicher Zuwendung, Zeit und einem ganzheitlichen Blick auf Gesundheit und Wohlbefinden.': [
        ['Вилла Циллнер — это место, где сочетаются медицинский профессионализм, спокойствие и элегантная атмосфера. Она символизирует индивидуальный подход к пациентам в особой обстановке, создающей ощущение доверия, конфиденциальности и комфорта.'],
        ['Элегантная архитектура и спокойная атмосфера виллы создают идеальные условия для современной медицинской практики. Здесь профессиональная медицинская помощь сочетается с обстановкой, в которой пациенты могут чувствовать себя комфортно и уверенно.'],
        ['Вилла Циллнер — это не просто место расположения медицинской практики, а часть философии доктора Валерии Циллнер: медицина высокого уровня в сочетании с индивидуальным вниманием, временем для пациента и комплексным подходом к здоровью и благополучию.'],
    ],
    'In meiner Ordination biete ich eine umfassende medizinische Betreuung für Erwachsene und Kinder ab fünf Jahren an.Dazu gehören Diagnostik, Prävention, Behandlung akuter Erkrankungen sowie langfristige medizinische Begleitung.Zusätzlich begleite ich Patientinnen und Patienten bei Anästhesien in privaten Krankenhäusern in Wien und behandle akute sowie chronische Schmerzen.': [
        ['В своей медицинской практике я предлагаю комплексное медицинское обслуживание для взрослых и детей от пяти лет.',
         'Это включает диагностику, профилактику, лечение острых заболеваний, а также долгосрочное медицинское сопровождение.',
         'Кроме того, я сопровождаю пациентов во время анестезии в частных клиниках Вены и занимаюсь лечением как острых, так и хронических болевых состояний.'],
    ],
}
SPLIT_PAIRS = {
    'Die Ordination von Dr. Valeria Zillner bietet umfassende medizinische Betreuung, Prävention und moderne Diagnostik für Erwachsene und Kinder.':
        'Медицинская практика доктора Валерии Циллнер предлагает комплексное медицинское обслуживание, профилактику и современную диагностику для взрослых и детей.',
    'Gesundheit ist nicht alles, aber ohne Gesundheit ist alles nichts.“': '«Здоровье — это ещё не всё, но без здоровья всё — ничто».',
    '— Arthur Schopenhauer': '— Артур Шопенгауэр',
    'Villa Zillner': 'Вилла Циллнер',
    'Ärztin für Allgemeinmedizin und Fachärztin für Anästhesiologie': 'Врач общей практики и врач-специалист по анестезиологии',
    '„Die größte Sorge ist der Gesundheit.“': '«Самая большая забота — это здоровье».',
    '„Wir haben kein Recht, die Zeugnisse der Vergangenheit anzutasten. Sie gehören nicht uns, sondern den kommenden Generationen.“':
        '«Мы не имеем права вмешиваться в наследие прошлого. Оно принадлежит не нам, а будущим поколениям».',
}
SPLIT_RE = re.compile(r'(?:<span style="display:inline-block;[^"]*">[^<]*</span> ?)+')
SPLIT_WORD_RE = re.compile(r'<span style="(display:inline-block;[^"]*)">([^<]*)</span>')

HANDOVER_RE = re.compile(r'(<script id="__framer__handoverData" type="framer/handover">)(.*?)(</script>)', re.S)


def load_items(locale):
    items = read_chunk((FRAMER / f'Bzbs7oMUB-chunk-{locale}-0.framercms').read_bytes())
    out = {}
    for item in items:
        d = {k: v[1] for k, v in item if v is not None}
        d[CONTENT] = d[CONTENT][1]  # rich text is stored inline as JSON
        out[d['id']] = d
    return out


def richtext_html(rt):
    """Renders Framer rich text JSON the way Framer's SSR does for these pages."""
    def node(n):
        if n[0] == 5:
            return html.escape(n[1], quote=False)
        _, tag, attrs, *children = n
        attrs = dict(attrs or {})
        cls = ['framer-text']
        if tag in ('p', 'li'):
            cls.append(PRESET)
        if 'className' in attrs:
            cls.append(attrs.pop('className'))
        a = ''.join(f' {k}="{html.escape(str(v))}"' for k, v in attrs.items())
        if tag == 'br':
            return f'<br class="{" ".join(cls)}"{a}/>'
        return f'<{tag} class="{" ".join(cls)}"{a}>{"".join(node(c) for c in children)}</{tag}>'
    return ''.join(node(n) for n in json.loads(rt)[1:])


def text_node(s):
    return '>' + html.escape(s, quote=False) + '<'


def blank_unreferenced(data):
    """Empties strings no longer reachable in a devalue-encoded handover array (old CMS
    values replaced by sync_cms), keeping indices stable."""
    seen, todo = set(), [0]
    while todo:
        i = todo.pop()
        if not isinstance(i, int) or i < 0 or i in seen:
            continue
        seen.add(i)
        v = data[i]
        if isinstance(v, dict):
            todo.extend(v.values())
        elif isinstance(v, list):
            todo.extend(v[1:] if v and isinstance(v[0], str) else v)
    for i, v in enumerate(data):
        if i not in seen and isinstance(v, str):
            data[i] = ''


def sync_cms(page, slug, items, locale):
    """Replaces the CMS values of item `slug` (and its prev/next titles) in a CMS page:
    both the server-rendered text and the embedded handover data."""
    m = HANDOVER_RE.search(page)
    data = json.loads(m.group(2))
    record = next(x for x in data if isinstance(x, dict) and TITLE in x and CONTENT in x)
    target = next(i for i in items.values() if i[SLUG] == slug)
    replacements = []

    def value(key):
        return data[data[record[key]]['value']]

    def set_value(key, new, label='{}'):
        old = value(key)
        if old == new:
            return
        replacements.append((text_node(label.format(old)), text_node(label.format(new))))
        # Append instead of overwriting: devalue shares identical values between fields.
        data.append(new)
        data[record[key]] = dict(data[record[key]], value=len(data) - 1)

    for key in (TITLE, DESCRIPTION, SUBHEADING):
        set_value(key, target[key])
    for rel, label in (('previousItemId', '‹ {}'), ('nextItemId', '{} ›')):
        if rel in record and data[record[rel]] is not None:
            set_value(f'{rel}.{TITLE}', items[value(rel)][TITLE], label)

    rt = value(CONTENT)
    collection_id = f'{COLLECTION}{locale}'
    if data[rt['pointer']] != target[CONTENT] or data[rt['collectionId']] != collection_id:
        replacements.append((richtext_html(data[rt['pointer']]), richtext_html(target[CONTENT])))
        data.append(target[CONTENT])
        data.append(collection_id)
        data.append({'collectionId': len(data) - 1, 'pointer': len(data) - 2})
        data[record[CONTENT]] = dict(data[record[CONTENT]], value=len(data) - 1)

    for old, new in replacements:
        assert old in page, f'{slug}: SSR text not found: {old[:80]}'
        page = page.replace(old, new)
    blank_unreferenced(data)
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    return HANDOVER_RE.sub(lambda mm: mm.group(1) + payload + mm.group(3), page, count=1)


def localize(page, url_path, ssr_dict):
    page = page.replace('<html lang="de-AT">', '<html lang="ru-RU">', 1)
    page = page.replace('"localeId":"default"', f'"localeId":"{RU}"', 1)
    ru_url = SITE + '/ru' + ('/' if url_path == '/' else url_path)
    de_url = SITE + url_path
    page = page.replace(f'<link href="{de_url}" rel="canonical"/>', f'<link href="{ru_url}" rel="canonical"/>')
    page = page.replace(f'<meta content="{de_url}" property="og:url"/>', f'<meta content="{ru_url}" property="og:url"/>')
    page = re.sub(r'href="/(?!ru/|/|framer/)([^"]*)"', lambda m: f'href="/ru/{m.group(1)}"', page)
    # Framer's locale picker server-renders only the current locale.
    page = page.replace('<option selected="" value="default">German</option>',
                        f'<option selected="" value="{RU}">Русский</option>')

    def tr_text(m):
        t = html.unescape(m.group(1))
        key = ' '.join(t.split())
        if key in ssr_dict:
            lead = t[:len(t) - len(t.lstrip())]
            trail = t[len(t.rstrip()):]
            return '>' + html.escape(lead + ssr_dict[key] + trail, quote=False) + '<'
        return m.group(0)

    head_end = page.index('</head>')
    head, body = page[:head_end], page[head_end:]
    # <title> and meta content in the head
    head = re.sub(r'<title>([^<]*)</title>',
                  lambda m: '<title>' + html.escape(ssr_dict.get(html.unescape(m.group(1)), html.unescape(m.group(1))), quote=False) + '</title>', head)
    head = re.sub(r'(<meta content=")([^"]*)(" (?:name|property)="(?:description|og:title|og:description|twitter:title|twitter:description)"/>)',
                  lambda m: m.group(1) + html.escape(ssr_dict.get(html.unescape(m.group(2)), html.unescape(m.group(2)))) + m.group(3), head)
    def tr_split(m):
        words = SPLIT_WORD_RE.findall(m.group(0))
        ru = SPLIT_PAIRS.get(html.unescape(' '.join(w for _, w in words)))
        if ru is None:
            return m.group(0)
        style = words[0][0]
        trail = ' ' if m.group(0).endswith(' ') else ''
        return ' '.join(f'<span style="{style}">{html.escape(w, quote=False)}</span>' for w in ru.split()) + trail

    def tr_struct(text, paragraphs):
        words = r'\s+'.join(re.escape(html.escape(w, quote=False)) for w in text.split())
        pattern = re.compile(r'(<p [^>]*>)\s*' + words + r'\s*</p>')
        lines = lambda p: '<br class="framer-text"/>'.join(html.escape(t, quote=False) for t in p)
        return lambda s: pattern.sub(lambda m: ''.join(m.group(1) + lines(p) + '</p>' for p in paragraphs), s)

    # text nodes in the body, outside <script>/<style>
    parts = re.split(r'(<script\b.*?</script>|<style\b.*?</style>)', body, flags=re.S)
    for i in range(0, len(parts), 2):
        for text, paragraphs in STRUCT_PAIRS.items():
            parts[i] = tr_struct(text, paragraphs)(parts[i])
        parts[i] = SPLIT_RE.sub(tr_split, parts[i])
        parts[i] = re.sub(r'>([^<>]+)<', tr_text, parts[i])
        parts[i] = re.sub(r'placeholder="([^"]*)"',
                          lambda m: 'placeholder="%s"' % html.escape(ssr_dict.get(html.unescape(m.group(1)), html.unescape(m.group(1)))),
                          parts[i])
    return head + ''.join(parts)


def main():
    ssr_dict = json.loads(DICT.read_text(encoding='utf8')) if DICT.exists() else {}
    de_items, ru_items = load_items('default'), load_items(RU)
    # Head texts Framer doesn't localize at runtime, and the CMS page titles.
    ssr_dict.update(DESCRIPTION_RU)
    ssr_dict.update(MANUAL_PAIRS)
    for item_id, de in de_items.items():
        ssr_dict[f'{de[TITLE]} | Avrix'] = f'{ru_items[item_id][TITLE]} | Avrix'
    jobs = [(p, '/' if p == 'index.html' else '/' + p[:-5]) for p in PAGES]
    jobs += [(f'behandlung/{f.name}', f'/behandlung/{f.stem}') for f in sorted((ROOT / 'behandlung').glob('*.html'))]
    for rel, url_path in jobs:
        src = ROOT / rel
        page = src.read_text(encoding='utf8')
        ru_page = page
        if rel.startswith('behandlung/'):
            slug = pathlib.Path(rel).stem
            page = sync_cms(page, slug, de_items, 'default')
            src.write_text(page, encoding='utf8', newline='')
            ru_page = sync_cms(page, slug, ru_items, RU)
        out = ROOT / 'ru' / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        page_dict = {**ssr_dict, **PAGE_PAIRS.get(rel, {})}
        out.write_text(localize(ru_page, url_path, page_dict), encoding='utf8', newline='')
    print(f'wrote {len(jobs)} Russian pages')


if __name__ == '__main__':
    main()
