export interface DatagrepperResult {
    arguments:    Arguments;
    count:        number;
    pages:        number;
    raw_messages: RawMessage[];
    total:        number;
}

export interface Arguments {
    categories:     string[];
    contains:       string[];
    delta?:         number;
    end?:           number;
    grouped:        boolean;
    meta:           string[];
    not_categories: string[];
    not_packages:   string[];
    not_topics:     string[];
    not_users:      string[];
    order:          string;
    packages:       string[];
    page:           number;
    rows_per_page:  number;
    start?:         number;
    topics:         string[];
    users:          string[];
}

export interface RawMessage {
    certificate:    string;
    crypto:         string;
    headers:        {};
    i:              number;
    meta:           Meta;
    msg:            Msg;
    msg_id:         string;
    signature:      string;
    source_name:    string;
    source_version: string;
    timestamp:      number;
    topic:          string;
    username:       string;
}

export interface Meta {
    icon:     string;
    link:     string;
    subtitle: string;
    date:     string;
}

export interface Msg {
    [key: string]: any;
}
