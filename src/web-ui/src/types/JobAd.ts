export interface JobAd {
    id: string;
    date_added: number;
    description: string;
    link: string;
    is_qualified: boolean;
    processed: boolean;
    title: string;
    company: string;
    date_processed: number;
}