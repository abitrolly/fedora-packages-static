import { DatagrepperResult, Meta } from "./types/datagrepper";

export class DgConnector {
    endpoint: string;

    constructor(dgEndpoint: string) {
        this.endpoint = dgEndpoint;
    }

    async getMessages(packageName: string, opts?: { page?: number }) {
        const queryURL = new URL(this.endpoint);
        queryURL.pathname += "/raw";
        queryURL.searchParams.append("package", packageName);
        queryURL.searchParams.append("meta", "subtitle");
        queryURL.searchParams.append("meta", "link");
        queryURL.searchParams.append("meta", "icon");
        queryURL.searchParams.append("meta", "date");
        queryURL.searchParams.append("not_topic", "org.fedoraproject.prod.mdapi.repo.update");
        queryURL.searchParams.append("not_topic", "org.fedoraproject.prod.buildsys.rpm.sign");
        queryURL.searchParams.append("not_topic", "org.fedoraproject.prod.buildsys.tag");
        queryURL.searchParams.append("not_topic", "org.fedoraproject.prod.buildsys.untag");
        queryURL.searchParams.append("not_topic", "org.fedoraproject.prod.buildsys.package.list.change");
        if (opts?.page) {
            queryURL.searchParams.append("page", String(opts.page));
        }

        try {
            const request = await fetch(queryURL.href);
            if (!request.ok) {
                console.error("Request error:", request);
                return "Error: Could not connect to Datagrepper";
            }
            const response = await request.json() as DatagrepperResult;

            let messages = [] as Messages[];
            for (const msg of response.raw_messages) {
                messages.push({...msg.meta, id: msg.msg_id});
            }
            
            return {
                messages,
                pages: response.pages,
                page: response.arguments.page,
            }
        } catch (e) {
            return String(e);
        }
    }
}

export interface Messages extends Meta {
    id: string;
} 
