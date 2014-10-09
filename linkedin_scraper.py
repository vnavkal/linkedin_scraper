import re
from bs4 import BeautifulSoup
import cookielib
import urllib2
import mechanize
import json
import pandas as pd

path = '/home/viraj/upstart_share/shared_data/directmail_data/'
df = pd.read_excel(path + "directmail_data.xls", 0)

class LinkedInBrowser:

    username = "virajisanavkal@gmail.com"
    password = "QfmdCGwpDxfP"

    def __init__(self):
        self.br = mechanize.Browser()
        self.br.addheaders = [('User-agent','Mozilla/5.0')]
        self.br.set_handle_equiv(True)
        self.br.set_handle_gzip(True)
        self.br.set_handle_redirect(True)
        self.br.set_handle_referer(True)
        self.br.set_handle_robots(False)

        # Follows refresh 0 but not hangs on refresh > 0
        self.br.set_handle_refresh(mechanize._http.HTTPRefreshProcessor(), max_time=1)

        # Enable cookie support for urllib2 
        cookiejar = cookielib.LWPCookieJar() 
        self.br.set_cookiejar(cookiejar)


        print 'Logging in...'
        base_url = 'https://www.linkedin.com'
        self.br.open(base_url)
        self.br.select_form(name="login")
        self.br["session_key"] = self.username
        self.br["session_password"] = self.password
        self.br.submit()

    def find_all_attributes(self, first_name, last_name, school):
        google_data = self.google_search(first_name, last_name, school)
        tag = self.get_matching_tag_from_google_data(google_data, first_name, last_name)
        if tag is None:
            print "Could not find any information for %s %s" % (first_name, last_name)
            return None

        google_info = self.get_info_from_matching_tag(tag)

        link = self.get_linkedin_profile_link_from_matching_tag(first_name, last_name, tag)
        linkedin_data = self.get_linkedin_data_from_link(link)

        return {'google': google_info, 'linkedin': linkedin_data}

    def linkedin_search(self, first_name, last_name, school):
        first_name = first_name.replace(" ", "%20")
        last_name = last_name.replace(" ", "%20")
        school = school.replace(" ", "%20")

        url = "https://www.linkedin.com/vsearch/p?firstName=%s&lastName=%s&school=%s&openAdvancedForm=true&locationType=I&countryCode=us&rsid=3714621781412546130648&orig=MDYS" % (first_name, last_name, school)
        html = self.br.open(url)
        soup = BeautifulSoup(html)
        return soup

    def google_search(self, first_name, last_name, school):
        print "Searching for %s %s in Google..." % (first_name, last_name)
        self.br.open("http://google.com")
        self.br.select_form( 'f' )
        self.br.form[ 'q' ] = " ".join([first_name, last_name, school, "inurl:linkedin.com"])
        response = self.br.submit()

        google_data = response.get_data()

        return google_data

    def get_matching_tag_from_google_data(self, google_data, first_name, last_name):
        soup = BeautifulSoup(google_data)
        return soup.find(lambda tag: self.tag_matches(tag, first_name, last_name))

    def get_linkedin_profile_link_from_matching_tag(self, first_name, last_name, matching_tag):
        return re.search(self.link_pattern(first_name, last_name), matching_tag.a['href']).group(1)

    def get_info_from_matching_tag(self, matching_tag):
        subheader = matching_tag.find('div', class_='f slp')
        if subheader is None:
            return None
        info_text = subheader.text
        location, employment = re.split(r'(?:\xa0\-\xa0)', info_text)
        # location, title, company = re.split(r'(?:\xa0\-\xa0| ?at )', info_text)
        split_location = location.split(',')
        split_employment = re.split(r'(?: ?at )', employment)
        if len(split_employment) == 1:
            split_employment = re.split(r',', employment)
        if len(split_employment) == 1:
            job_title, company = split_employment[0], None
        else:
            job_title, company = split_employment[-2:]
        if len(split_location) > 1:
            city, state = split_location[-2:]
        else:
            city, state = split_location[0], None
        return {'city': city, 'state': state, 'job_title': job_title, 'company': company}

    def get_linkedin_data_from_link(self, link):
        content = self.br.open(link).get_data()
        job_titles = self.get_job_titles_from_content(content)
        current_job = self.get_current_job_from_content(content)
        return {'job_titles': job_titles, 'current_job': current_job}

    def get_job_titles_from_content(self, content):
        print "Scanning LinkedIn profile page for job titles..."
        section_pattern = '"Experience":.*?"positions":(\[.*?\])(?:,"showSection"|,"deferImg"|,"firstTopCurrentPosition"|"visible"|"find_title"|}).*?,"Volunteering":'
        # section_pattern = '"Experience":.*?"positions":(\[[^\[]*?\]|FINISH THIS UP)(?:,"showSection"|,"deferImg"|,"firstTopCurrentPosition"|"visible"|"find_title"|}).*?,"Volunteering":'
        match = re.search(section_pattern, content)
        if match is None:
            print "Could not find any jobs on LinkedIn page"
            return []
        else:
            experience_json = match.group(1)
            try:
                parsed_json = json.loads(experience_json)
            except ValueError:
                parsed_json = []
            return [item['title'] for item in parsed_json]

    def get_current_job_from_content(self, content):
        print "Scanning LinkedIn profile page for current job title..."
        section_pattern = '"firstTopCurrentPosition":({.*?})'
        match = re.search(section_pattern, content)
        if match is None:
            print "Could not find current job on LinkedIn page"
            return None
        else:
            experience_json = match.group(1)
            return json.loads(experience_json)['title']

    def tag_matches(self, tag, first_name, last_name):
        if not (tag.name == 'li' and tag.has_attr('class') and tag['class'] == ['g']):
            return False
        descendants_with_matching_links = tag.find_all('a', href=self.link_pattern(first_name, last_name))
        return (len(descendants_with_matching_links) > 0)

    def link_pattern(self, first_name, last_name):
        return re.compile('(http://www.linkedin.com/pub/%s-(:?.*?)%s/(:?.*?))&' % (first_name.replace(" ", "-").lower(), last_name.replace(" ", "-").lower()))

def directmail_employment_info(rows):
    lib = LinkedInBrowser()
    df_with_employment = df.copy()

    for row_number in rows:
        first_name, last_name, school = df.loc[row_number, ['student first', 'student last', 'school name']]
        print "Finding information for %s %s who attended %s, found in row %s of the table." % (first_name, last_name, school, row_number)
        df_with_employment['google_city'] = None
        df_with_employment['google_state'] = None
        df_with_employment['google_company'] = None
        df_with_employment['google_job_title'] = None
        df_with_employment['linkedin_job_titles'] = None
        df_with_employment['linkedin_current_job'] = None
        all_attributes = lib.find_all_attributes(first_name, last_name, school)
        if all_attributes is not None:
            if all_attributes['google'] is not None:
                df_with_employment.loc[row_number, ['google_city']] = all_attributes['google']['city']
                df_with_employment.loc[row_number, ['google_state']] = all_attributes['google']['state']
                df_with_employment.loc[row_number, ['google_company']] = all_attributes['google']['company']
                df_with_employment.loc[row_number, ['google_job_title']] = all_attributes['google']['job_title']
            df_with_employment.loc[row_number, ['linkedin_current_job']] = all_attributes['linkedin']['current_job']
            df_with_employment.loc[row_number, ['linkedin_job_titles']] = str(all_attributes['linkedin']['job_titles'])
    return df_with_employment
