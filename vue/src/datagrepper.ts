import { DatagrepperResult, Meta } from "./types/datagrepper";

export class DgConnector {
    endpoint: string;

    constructor(dgEndpoint: string) {
        this.endpoint = dgEndpoint;
    }

    async getMessages(packageName: string, opts?: { page?: number, delta?: number; end?: number; start?: number }):
        Promise<string | { messages: Messages[]; pages: number; page: number; count: number; }> {
        const queryURL = new URL(this.endpoint);
        queryURL.pathname += "/raw";
        queryURL.searchParams.append("package", packageName);
        queryURL.searchParams.append("meta", "title");
        queryURL.searchParams.append("meta", "subtitle");
        queryURL.searchParams.append("meta", "link");
        queryURL.searchParams.append("meta", "icon");
        queryURL.searchParams.append("meta", "date");
        queryURL.searchParams.append("not_topic", "org.fedoraproject.prod.mdapi.repo.update");
        queryURL.searchParams.append("not_topic", "org.fedoraproject.prod.buildsys.rpm.sign");
        queryURL.searchParams.append("not_topic", "org.fedoraproject.prod.buildsys.tag");
        queryURL.searchParams.append("not_topic", "org.fedoraproject.prod.buildsys.untag");
        queryURL.searchParams.append("not_topic", "org.fedoraproject.prod.buildsys.package.list.change");
        queryURL.searchParams.append("not_topic", "org.release-monitoring.prod.anitya.project.version.update.v2");
        if (opts?.page) {
            queryURL.searchParams.append("page", String(opts.page));
        }
        if (opts?.delta) {
            queryURL.searchParams.append("delta", String(opts.delta));
        }
        if (opts?.end) {
            queryURL.searchParams.append("end", String(opts.end));
        }
        if (opts?.start) {
            queryURL.searchParams.append("start", String(opts.start));
        }

        try {
            const request = await fetch(queryURL.href);
            if (!request.ok) {
                console.error("Request error:", request);
                return "Error: Could not connect to Datagrepper";
            }
            const response = await request.json() as DatagrepperResult;

            const messages = [] as Messages[];
            for (const msg of response.raw_messages) {
                messages.push({...msg.meta, id: msg.msg_id});
            }

            return {
                messages,
                pages: response.pages,
                page: response.arguments.page,
                count: response.count
            }
        } catch (e) {
            return String(e);
        }
    }
}

export interface Messages extends Meta {
    id: string;
}
